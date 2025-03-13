import { ReactNode } from 'react';

interface TableWrapperProps {
  children: ReactNode;
}

const TableWrapper: React.FC<TableWrapperProps> = ({ children }) => {
  return (
    <div className="w-full overflow-x-auto">
      <table>{children}</table>
    </div>
  );
};

export default TableWrapper;