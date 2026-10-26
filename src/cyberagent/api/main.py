from fastapi import FastAPI, HTTPException, Depends
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
import logging
import json
from typing import AsyncGenerator
import pandas as pd  # We need pandas for the flow metadata endpoint
import asyncio
from concurrent.futures import ThreadPoolExecutor

from cyberagent.api import models
from cyberagent.investigation import (
    predict_proba,
    explain_flow,
    find_related_flows,
    similar_known_attacks,
    lookup_attack_pattern,
    _initialize_data_and_model,
    _model,
    _features_df_model,
)
import cyberagent.investigation as investigation_module
from cyberagent.agent.investigation_agent import investigate_flow
from cyberagent.config import config
from cyberagent.logging_setup import logger

# Thread pool for running blocking investigation tasks
executor = ThreadPoolExecutor(max_workers=4)

# Initialize FastAPI app
app = FastAPI(
    title="CyberAgent API",
    description="API for CyberAgent: Agent-Assisted Network Threat Detection and Investigation using Machine Learning",
    version="0.1.0",
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=config.get("api.cors_origins", []),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class StripPrefixMiddleware:
    """Strip a fixed path prefix (e.g. /api on Vercel, where rewrites keep the
    prefix). Set API_PATH_PREFIX=/api in the deployment env; unset = routes at root."""

    def __init__(self, asgi_app, prefix: str):
        self.asgi_app = asgi_app
        self.prefix = prefix.rstrip("/")

    async def __call__(self, scope, receive, send):
        if scope["type"] in ("http", "websocket") and self.prefix:
            path = scope.get("path", "")
            root = scope.get("root_path", "")
            if path.startswith(root + self.prefix):
                new_path = path[len(root + self.prefix):] or "/"
                scope = dict(scope)
                scope["path"] = new_path
                scope["raw_path"] = new_path.encode()
        await self.asgi_app(scope, receive, send)

import os as _os
_prefix = _os.environ.get("API_PATH_PREFIX", "")
if _prefix:
    app.add_middleware(StripPrefixMiddleware, prefix=_prefix)
    logger.info(f"API routes mounted under prefix: {_prefix}")

# Health check endpoint
@app.get("/health", response_model=models.HealthResponse)
async def health_check():
    return models.HealthResponse(status="healthy")

# Model status endpoint
@app.get("/model/status", response_model=models.ModelStatusResponse)
async def model_status():
    try:
        _initialize_data_and_model()
        # Use module references to get updated values
        model = investigation_module._model
        features_df_model = investigation_module._features_df_model
        if model is not None:
            model_type = type(model).__name__
            feature_count = features_df_model.shape[1] if features_df_model is not None else None
            classes = getattr(model, 'classes_', None)
            if classes is not None:
                classes = [str(c) for c in classes]
            else:
                # For models with label encoder
                if hasattr(model, 'label_encoder_'):
                    classes = [str(c) for c in model.label_encoder_.classes_]
                else:
                    classes = None
            return models.ModelStatusResponse(
                model_loaded=True,
                model_type=model_type,
                feature_count=feature_count,
                classes=classes
            )
        else:
            return models.ModelStatusResponse(model_loaded=False)
    except Exception as e:
        logger.error(f"Error checking model status: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

# Predict endpoint
@app.post("/predict", response_model=models.PredictResponse)
async def predict(request: models.PredictRequest):
    try:
        result = predict_proba(request.flow_id)
        return models.PredictResponse(
            flow_id=result['flow_id'],
            predicted_class=result['predicted_class'],
            confidence=result['confidence'],
            probabilities=result['probabilities']
        )
    except ValueError as e:
        logger.warning(f"Flow ID not found: {request.flow_id}")
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Error during prediction: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

# Flow metadata endpoint
@app.get("/flow/{flow_id}", response_model=models.FlowMetadataResponse)
async def get_flow_metadata(flow_id: int):
    try:
        _initialize_data_and_model()
        # Use the module reference to get the updated _metadata_df
        metadata_df = investigation_module._metadata_df
        if metadata_df is None:
            raise RuntimeError("Metadata not initialized")
        # Find the row with matching flow_id
        mask = metadata_df['flow_id'] == flow_id
        if not mask.any():
            raise ValueError(f"Flow ID {flow_id} not found in dataset")
        row = metadata_df.iloc[mask.index[0]]
        # Extract the required fields
        return models.FlowMetadataResponse(
            flow_id=int(row['flow_id']),
            source_ip=str(row.get('Source IP', '')),
            source_port=int(row.get('Source Port', 0)) if pd.notna(row.get('Source Port')) else None,
            destination_ip=str(row.get('Destination IP', '')),
            destination_port=int(row.get('Destination Port', 0)) if pd.notna(row.get('Destination Port')) else None,
            protocol=str(row.get('Protocol', '')),
            timestamp=row.get('Timestamp') if pd.notna(row.get('Timestamp')) else None
        )
    except ValueError as e:
        logger.warning(f"Flow ID not found: {flow_id}")
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Error retrieving flow metadata: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

# Investigation endpoint with SSE support
@app.post("/investigate")
async def investigate(request: models.PredictRequest):
    logger.info(f"Starting investigation for flow_id: {request.flow_id}")

    async def event_generator() -> AsyncGenerator[str, None]:
        loop = asyncio.get_event_loop()
        queue: asyncio.Queue = asyncio.Queue()

        def on_event(ev: dict):
            # Thread-safe push of tool-call progress from the worker thread
            loop.call_soon_threadsafe(queue.put_nowait, ev)

        yield f"event: start\n"
        yield f"data: {json.dumps({'flow_id': request.flow_id})}\n\n"

        task = loop.run_in_executor(executor, lambda: investigate_flow(request.flow_id, on_event=on_event))

        try:
            while not task.done():
                try:
                    ev = await asyncio.wait_for(queue.get(), timeout=0.5)
                    yield f"event: progress\n"
                    yield f"data: {json.dumps(ev)}\n\n"
                except asyncio.TimeoutError:
                    continue
            # Drain any events queued between done() and the final await
            while not queue.empty():
                ev = queue.get_nowait()
                yield f"event: progress\n"
                yield f"data: {json.dumps(ev)}\n\n"

            result = await task
            if result.get('predicted_class') == 'UNKNOWN' or 'error' in str(result.get('verdict', '')).lower():
                logger.error(f"Investigation returned error: {result.get('verdict')}")
                yield f"event: error\n"
                yield f"data: {json.dumps({'error': result.get('verdict', 'Investigation failed')})}\n\n"
            else:
                yield f"event: end\n"
                yield f"data: {json.dumps(result)}\n\n"
        except Exception as e:
            logger.error(f"Error during investigation: {e}")
            yield f"event: error\n"
            yield f"data: {json.dumps({'error': str(e)})}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")

# We'll also add a root endpoint for convenience
@app.get("/")
async def root():
    return {"message": "Welcome to the CyberAgent API"}