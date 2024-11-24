import struct
from typing import List
import tkinter as tk
from tkinter import filedialog, messagebox
from tkinter import ttk
import tkinter.font as tkfont  # Import the font module


class STB:
    def __init__(self, file_path: str = None):
        self.file_path: str = file_path
        self.row_size: int = 0
        self.column_sizes: List[int] = []
        self.column_names: List[str] = []
        self.cells: List[List[str]] = []
        self.encoding: str = 'euc-kr'  # Encoding used in the STB files

        if file_path:
            self.load(file_path)

    def load(self, file_path: str):
        with open(file_path, 'rb') as f:
            self.file_path = file_path

            # Read header
            magic = f.read(4)
            if magic not in (b'STB0', b'STB1'):
                raise ValueError('Invalid STB file.')

            data_offset = struct.unpack('<I', f.read(4))[0]
            row_count = struct.unpack('<I', f.read(4))[0]
            column_count = struct.unpack('<I', f.read(4))[0]
            self.row_size = struct.unpack('<I', f.read(4))[0]

            # Read column sizes
            self.column_sizes = []
            for _ in range(column_count + 1):
                size_data = f.read(2)
                if not size_data:
                    break
                size = struct.unpack('<h', size_data)[0]
                self.column_sizes.append(size)

            # Read column names
            self.column_names = []
            for _ in range(column_count + 1):
                name_length_data = f.read(2)
                if not name_length_data:
                    break
                name_length = struct.unpack('<h', name_length_data)[0]
                name_data = f.read(name_length)
                name = name_data.decode(self.encoding)
                self.column_names.append(name)

            # Read row names (first cell of each row)
            self.cells = []
            for _ in range(row_count - 1):
                row = []
                name_length_data = f.read(2)
                if not name_length_data:
                    break
                name_length = struct.unpack('<h', name_length_data)[0]
                name_data = f.read(name_length)
                name = name_data.decode(self.encoding)
                row.append(name)
                self.cells.append(row)

            # Seek to data offset if necessary
            current_position = f.tell()
            if current_position < data_offset:
                f.seek(data_offset)

            # Read the rest of the cells
            for row in self.cells:
                for _ in range(column_count - 1):
                    cell_length_data = f.read(2)
                    if not cell_length_data:
                        break
                    cell_length = struct.unpack('<h', cell_length_data)[0]
                    cell_data = f.read(cell_length)
                    cell = cell_data.decode(self.encoding)
                    row.append(cell)

    def save(self, file_path: str = None):
        if file_path is None:
            file_path = self.file_path

        with open(file_path, 'wb') as f:
            # Write header
            f.write(b'STB1')

            # Placeholder for data offset
            data_offset_position = f.tell()
            f.write(struct.pack('<I', 0))  # Placeholder

            # Calculate row and column counts
            row_count = len(self.cells) + 1  # Include header row
            column_count = max(len(row) for row in self.cells) if self.cells else 0

            f.write(struct.pack('<I', row_count))
            f.write(struct.pack('<I', column_count))
            f.write(struct.pack('<I', self.row_size))

            # Write column sizes
            if not self.column_sizes:
                # Initialize column sizes to zero if not set
                self.column_sizes = [0] * (column_count + 1)

            for size in self.column_sizes:
                f.write(struct.pack('<h', size))

            # Write column names
            for name in self.column_names:
                name_bytes = name.encode(self.encoding)
                f.write(struct.pack('<h', len(name_bytes)))
                f.write(name_bytes)

            # Write row names (first cell of each row)
            for row in self.cells:
                name_bytes = row[0].encode(self.encoding)
                f.write(struct.pack('<h', len(name_bytes)))
                f.write(name_bytes)

            # Record data offset
            data_offset = f.tell()

            # Write the rest of the cells
            for row in self.cells:
                for cell in row[1:]:
                    cell_bytes = cell.encode(self.encoding)
                    f.write(struct.pack('<h', len(cell_bytes)))
                    f.write(cell_bytes)

            # Go back and update data offset
            f.seek(data_offset_position)
            f.write(struct.pack('<I', data_offset))

    def set_cell(self, row: int, column: int, value: str):
        if row < 0 or row >= len(self.cells):
            raise IndexError('Row index out of range.')

        if column < 0:
            raise IndexError('Column index cannot be negative.')

        # Extend the row if necessary
        while len(self.cells[row]) <= column:
            self.cells[row].append('')

        self.cells[row][column] = value

    def get_cell(self, row: int, column: int) -> str:
        if row < 0 or row >= len(self.cells):
            raise IndexError('Row index out of range.')

        if column < 0 or column >= len(self.cells[row]):
            return ''

        return self.cells[row][column]

    def add_row(self, row_data: List[str]):
        self.cells.append(row_data)

    def add_column(self, column_name: str, default_value: str = ''):
        self.column_names.append(column_name)
        self.column_sizes.append(0)  # Adjust size as needed

        for row in self.cells:
            row.append(default_value)

    def get_row_count(self) -> int:
        return len(self.cells)

    def get_column_count(self) -> int:
        return len(self.column_names)


class STBEditorGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("STB Editor")

        self.stb = None

        # Initialize lists to manage columns
        self.all_columns = []        # All column identifiers
        self.hidden_columns = []     # Columns to be hidden ("Null" or "N/A")

        # Variable to track the state of showing hidden columns
        self.show_hidden_columns = tk.BooleanVar(value=False)

        # Column mapping: Treeview column ID -> actual column index in self.stb.column_names
        self.column_mapping = {}

        self.create_widgets()

    def create_widgets(self):
        # Create menu
        menubar = tk.Menu(self.root)

        # File menu
        file_menu = tk.Menu(menubar, tearoff=0)
        file_menu.add_command(label="Open", command=self.open_stb)
        file_menu.add_command(label="Save", command=self.save_stb)
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self.root.destroy)  # Fixed Exit command
        menubar.add_cascade(label="File", menu=file_menu)

        # View menu
        view_menu = tk.Menu(menubar, tearoff=0)
        view_menu.add_checkbutton(label="Show Hidden Columns",
                                  variable=self.show_hidden_columns,
                                  command=self.toggle_hidden_columns)
        menubar.add_cascade(label="View", menu=view_menu)

        self.root.config(menu=menubar)

        # Create a frame for the Treeview and scrollbars
        tree_frame = ttk.Frame(self.root)
        tree_frame.pack(fill=tk.BOTH, expand=True)

        # Initialize the Style
        style = ttk.Style()
        style.theme_use("default")  # Use default theme for consistency

        # Define a new font
        tree_font = tkfont.Font(family="Helvetica", size=10, weight="bold")  # Adjust as needed

        # Configure the Treeview style with enhanced visual features
        style.configure("Custom.Treeview",
                        background="white",
                        foreground="black",
                        rowheight=25,  # Increased row height for better readability
                        fieldbackground="white",
                        font=tree_font,
                        borderwidth=1,
                        relief="solid")  # Adds a solid border around the Treeview

        # Configure the heading style
        style.configure("Custom.Treeview.Heading",
                        font=('Helvetica', 12, 'bold'),
                        borderwidth=1,
                        relief="solid")  # Adds a solid border around the headings

        # Configure selection colors
        style.map('Custom.Treeview',
                  background=[('selected', '#347083')],
                  foreground=[('selected', 'white')])

        # Create the Treeview with the custom style
        self.tree = ttk.Treeview(tree_frame, style="Custom.Treeview")
        self.tree.bind('<Double-1>', self.on_cell_double_click)
        self.tree.grid(row=0, column=0, sticky='nsew')

        # Configure grid to allow the Treeview to expand
        tree_frame.grid_rowconfigure(0, weight=1)
        tree_frame.grid_columnconfigure(0, weight=1)

        # Create vertical scrollbar
        vsb = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL, command=self.tree.yview)
        vsb.grid(row=0, column=1, sticky='ns')
        self.tree.configure(yscrollcommand=vsb.set)

        # Create horizontal scrollbar
        hsb = ttk.Scrollbar(tree_frame, orient=tk.HORIZONTAL, command=self.tree.xview)
        hsb.grid(row=1, column=0, sticky='ew')
        self.tree.configure(xscrollcommand=hsb.set)

        # Add Status Bar
        self.status_bar = ttk.Label(self.root, text="Welcome to STB Editor", relief=tk.SUNKEN, anchor=tk.W)
        self.status_bar.pack(side=tk.BOTTOM, fill=tk.X)

        # Configure Tag Styles for Alternating Rows (Zebra Striping)
        self.tree.tag_configure('evenrow', background='aliceblue')  # Changed from 'lightblue' to 'aliceblue'
        self.tree.tag_configure('oddrow', background='white')

    def populate_tree(self):
        if not self.stb:
            return

        # Clear existing data
        for item in self.tree.get_children():
            self.tree.delete(item)

        # Initialize column lists
        self.all_columns = [f'col{idx}' for idx in range(1, len(self.stb.column_names))]
        self.hidden_columns = []  # Reset hidden columns

        # Identify columns to hide based on headers
        for idx, header in enumerate(self.stb.column_names[1:], start=1):
            if header in ["Null", "N/A"]:
                self.hidden_columns.append(f'col{idx}')

        # Determine visible columns based on the toggle
        if self.show_hidden_columns.get():
            visible_columns = self.all_columns.copy()
        else:
            visible_columns = [col for col in self.all_columns if col not in self.hidden_columns]

        # Define the "Row Name" column with unique identifier
        row_name_column = "row_name"
        visible_columns = [row_name_column] + visible_columns  # Ensure "Row Name" is first among data columns

        # Set the Treeview's columns (excluding #0 which will be used for "No.")
        self.tree['columns'] = visible_columns

        # Configure the #0 column (No.)
        self.tree.heading('#0', text='No.')
        self.tree.column('#0', width=50, minwidth=30, stretch=False, anchor='center')

        # Configure the "Row Name" column
        self.tree.heading(row_name_column, text='Row Name')
        self.tree.column(row_name_column, width=200, minwidth=150, stretch=False)

        # Configure other visible columns
        self.column_mapping = {}  # Reset column mapping
        for col_id in visible_columns[1:]:  # Skip "Row Name" as it's already configured
            # Find the header from stb.column_names
            try:
                col_number = int(col_id.replace('col', ''))
                header = self.stb.column_names[col_number]
                self.column_mapping[col_id] = col_number  # Map Treeview column to actual column index
            except (ValueError, IndexError):
                header = col_id  # Fallback to col_id if parsing fails
                self.column_mapping[col_id] = -1  # Invalid index
            self.tree.heading(col_id, text=header)
            self.tree.column(col_id, width=150, minwidth=100, stretch=False)

        # Insert data with row numbering and zebra striping
        total_rows = len(self.stb.cells)
        for row_idx, row_data in enumerate(self.stb.cells, start=0):
            values = row_data[1:]  # Exclude row name
            # Filter out values corresponding to hidden columns
            filtered_values = [
                value for idx, value in enumerate(values, start=1)
                if f'col{idx}' not in self.hidden_columns
            ]
            # Determine tag based on row index for zebra striping
            tag = 'evenrow' if row_idx % 2 == 0 else 'oddrow'
            # Insert the row with 'No.' and 'Row Name' + filtered values
            self.tree.insert(
                '', 'end', iid=str(row_idx), text=str(row_idx + 1),
                values=[row_data[0]] + filtered_values,
                tags=(tag,)
            )

        # Update the status bar with the total number of rows
        self.status_bar.config(text=f"Total Rows: {total_rows}")

    def toggle_hidden_columns(self):
        """Toggle the visibility of hidden columns based on the menu option."""
        self.populate_tree()

    def open_stb(self):
        file_path = filedialog.askopenfilename(
            title="Open STB File",
            filetypes=[("STB files", "*.stb"), ("All files", "*.*")]
        )
        if file_path:
            try:
                self.stb = STB(file_path)
                self.populate_tree()
                self.status_bar.config(text=f"Loaded: {file_path} | Total Rows: {len(self.stb.cells)}")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to open STB file:\n{e}")
                self.status_bar.config(text="Failed to load STB file.")

    def save_stb(self):
        if self.stb is None:
            messagebox.showwarning("Warning", "No STB file loaded.")
            return

        file_path = filedialog.asksaveasfilename(
            title="Save STB File",
            defaultextension=".stb",
            filetypes=[("STB files", "*.stb"), ("All files", "*.*")]
        )
        if file_path:
            try:
                self.stb.save(file_path)
                messagebox.showinfo("Success", "STB file saved successfully.")
                self.status_bar.config(text=f"Saved: {file_path} | Total Rows: {len(self.stb.cells)}")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to save STB file:\n{e}")
                self.status_bar.config(text="Failed to save STB file.")

    def on_cell_double_click(self, event):
        item_id = self.tree.focus()
        column = self.tree.identify_column(event.x)
        row = self.tree.identify_row(event.y)

        if item_id and column:
            # Retrieve row index from item_id
            try:
                row_index = int(item_id)
            except ValueError:
                messagebox.showerror("Error", "Invalid row identifier.")
                return

            # Retrieve column identifier
            column_id = self.tree.heading(column)['text']

            # Skip the 'No.' column
            if column_id == 'No.':
                return  # Do not allow editing the row number

            # Map column text to unique identifier
            # Find which column_id corresponds to which unique identifier
            # Reverse mapping: find the unique identifier whose heading is column_id
            unique_identifier = None
            for uid in self.tree['columns']:
                if self.tree.heading(uid)['text'] == column_id:
                    unique_identifier = uid
                    break

            if not unique_identifier:
                # Column not found, possibly an error
                messagebox.showerror("Error", f"Unknown column: {column_id}")
                return

            # Get the actual column index from the column mapping
            column_idx = self.column_mapping.get(unique_identifier, -1)

            if column_idx == -1:
                messagebox.showerror("Error", f"Invalid column mapping for: {unique_identifier}")
                return

            # Get current cell value using the unique identifier
            current_value = self.tree.set(item_id, unique_identifier)

            # Create a toplevel window for editing
            edit_window = tk.Toplevel(self.root)
            edit_window.title("Edit Cell")

            tk.Label(edit_window, text="Value:").pack(side=tk.LEFT, padx=5, pady=5)
            entry = tk.Entry(edit_window)
            entry.pack(side=tk.LEFT, padx=5, pady=5)
            entry.insert(0, current_value)
            entry.focus_set()

            def save_edit():
                new_value = entry.get()

                # Update the STB data
                try:
                    self.stb.set_cell(row_index, column_idx, new_value)
                except IndexError as ie:
                    messagebox.showerror("Error", f"Failed to set cell: {ie}")
                    edit_window.destroy()
                    return

                # Update the Treeview
                self.tree.set(item_id, unique_identifier, new_value)

                # Update the status bar to reflect changes
                self.status_bar.config(text=f"Edited Row {row_index + 1} | Total Rows: {len(self.stb.cells)}")

                edit_window.destroy()

            tk.Button(edit_window, text="Save", command=save_edit).pack(side=tk.LEFT, padx=5, pady=5)
            tk.Button(edit_window, text="Cancel", command=edit_window.destroy).pack(side=tk.LEFT, padx=5, pady=5)

            edit_window.transient(self.root)
            edit_window.grab_set()
            self.root.wait_window(edit_window)


def main():
    root = tk.Tk()
    app = STBEditorGUI(root)
    root.mainloop()


if __name__ == '__main__':
    main()
