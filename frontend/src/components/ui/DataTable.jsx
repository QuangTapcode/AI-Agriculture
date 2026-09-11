export function DataTable({ columns, rows, getRowKey = (row) => row.id, emptyMessage = 'Chưa có dữ liệu.' }) {
  if (!rows?.length) {
    return <p className="rounded-2xl border border-dashed border-slate-300 p-6 text-sm text-slate-500">{emptyMessage}</p>;
  }

  return (
    <div className="max-w-full overflow-x-auto rounded-2xl border border-slate-200 bg-white">
      <table className="w-full min-w-[680px] border-collapse text-left text-sm">
        <thead className="bg-slate-50 text-slate-500">
          <tr>{columns.map((column) => <th key={column.key} scope="col" className="px-5 py-3 font-semibold">{column.label}</th>)}</tr>
        </thead>
        <tbody className="divide-y divide-slate-100">
          {rows.map((row) => (
            <tr key={getRowKey(row)} className="transition-colors hover:bg-emerald-50/40">
              {columns.map((column) => <td key={column.key} className="px-5 py-4 text-slate-700">{column.render ? column.render(row) : row[column.key]}</td>)}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export default DataTable;
