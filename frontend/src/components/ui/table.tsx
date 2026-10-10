import * as React from "react";

const TableHeader = ({ children, className, ...props }: { children: React.ReactNode; className?: string; [key: string]: any }) => (
  <thead className={className} {...props}>
    {children}
  </thead>
);
TableHeader.displayName = "TableHeader";

const TableBody = ({ children, className, ...props }: { children: React.ReactNode; className?: string; [key: string]: any }) => (
  <tbody className={className} {...props}>
    {children}
  </tbody>
);
TableBody.displayName = "TableBody";

const TableFooter = ({ children, className, ...props }: { children: React.ReactNode; className?: string; [key: string]: any }) => (
  <tfoot className={className} {...props}>
    {children}
  </tfoot>
);
TableFooter.displayName = "TableFooter";

const TableCell = ({ children, className, ...props }: { children: React.ReactNode; className?: string; [key: string]: any }) => (
  <td className={className} {...props}>
    {children}
  </td>
);
TableCell.displayName = "TableCell";

const TableCaption = ({ children, className, ...props }: { children: React.ReactNode; className?: string; [key: string]: any }) => (
  <caption className={className} {...props}>
    {children}
  </caption>
);
TableCaption.displayName = "TableCaption";

const TableRow = ({ children, className, ...props }: { children: React.ReactNode; className?: string; [key: string]: any }) => (
  <tr className={className} {...props}>
    {children}
  </tr>
);
TableRow.displayName = "TableRow";

const Table = ({ children, className, ...props }: { children: React.ReactNode; className?: string; [key: string]: any }) => (
  <table className={`${className} min-w-full divide-y divide-navy-700`} {...props}>
    {children}
  </table>
);
Table.displayName = "Table";

export { Table, TableHeader, TableHeader as TableHead, TableBody, TableFooter, TableCell, TableCaption, TableRow };
