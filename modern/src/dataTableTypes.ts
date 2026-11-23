/** Row, patch and imperative contracts shared by the Tabulator adapter and its callers. */
export interface TableRow {
  id: string;
  rowtype?: string;
  has_children?: boolean;
  colour?: string | null;
}

export type TableRowPatch<Row extends TableRow> = Partial<Row> & Pick<Row, "id">;
export type TableView = { ids: string[]; position: { top: number; left: number } };

export interface DataTableHandle<Row extends TableRow> {
  focus: () => Promise<void>;
  patchRows: (updates: TableRowPatch<Row>[]) => Promise<void>;
  redraw: (force?: boolean) => Promise<void>;
  step: (event: KeyboardEvent, options?: { focus: boolean }) => Promise<void>;
  scrollToTop: () => Promise<void>;
  clearSelection: () => Promise<void>;
  viewState: () => TableView;
  restoreViewState: (view: TableView) => Promise<void>;
}
