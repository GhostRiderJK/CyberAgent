import * as React from "react";

export const CardHeader = ({ children, className, ...props }: { children: React.ReactNode; className?: string; [key: string]: any }) => (
  <div className={className} {...props}>
    {children}
  </div>
);
CardHeader.displayName = "CardHeader";

export const CardContent = ({ children, className, ...props }: { children: React.ReactNode; className?: string; [key: string]: any }) => (
  <div className={className} {...props}>
    {children}
  </div>
);
CardContent.displayName = "CardContent";

export const CardFooter = ({ children, className, ...props }: { children: React.ReactNode; className?: string; [key: string]: any }) => (
  <div className={className} {...props}>
    {children}
  </div>
);
CardFooter.displayName = "CardFooter";

export const CardTitle = ({ children, className, ...props }: { children: React.ReactNode; className?: string; [key: string]: any }) => (
  <h3 className={className} {...props}>
    {children}
  </h3>
);
CardTitle.displayName = "CardTitle";

export const CardDescription = ({ children, className, ...props }: { children: React.ReactNode; className?: string; [key: string]: any }) => (
  <p className={className} {...props}>
    {children}
  </p>
);
CardDescription.displayName = "CardDescription";

export const CardCaption = ({ children, className, ...props }: { children: React.ReactNode; className?: string; [key: string]: any }) => (
  <caption className={className} {...props}>
    {children}
  </caption>
);
CardCaption.displayName = "CardCaption";

export const Card = ({ children, className, ...props }: { children: React.ReactNode; className?: string; [key: string]: any }) => (
  <div className={`card ${className ?? ''}`} {...props}>
    {children}
  </div>
);
Card.displayName = "Card";