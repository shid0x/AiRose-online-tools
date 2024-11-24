import struct
import pandas as pd
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import os

def read_bstr(file):
    """Reads a length-prefixed string from the file."""
    current_pos = file.tell()
    lenstring_bytes = file.read(1)
    if not lenstring_bytes:
        print(f"Failed to read 1 byte for length at position {current_pos}.")
        return ''
    lenstring = struct.unpack('B', lenstring_bytes)[0]
    if lenstring > 127:
        extra_bytes = file.read(1)
        if not extra_bytes:
            print(f"Failed to read extra byte for length at position {current_pos}.")
            return ''
        extra = struct.unpack('B', extra_bytes)[0]
        lenstring = (lenstring - 128) + (extra * 128)
    # Read the string data
    string_bytes = file.read(lenstring)
    if len(string_bytes) < lenstring:
        print(f"Expected {lenstring} bytes at position {current_pos}, but got {len(string_bytes)} bytes.")
        return ''
    return string_bytes.decode('latin-1', errors='replace')

def write_bstr(file, text):
    """Writes a length-prefixed string to the file."""
    text_bytes = text.encode('latin-1', errors='replace')
    len_text = len(text_bytes)
    if len_text < 128:
        file.write(struct.pack('B', len_text))
    else:
        first_byte = (len_text % 128) + 128
        second_byte = len_text // 128
        file.write(struct.pack('B', first_byte))
        file.write(struct.pack('B', second_byte))
    file.write(text_bytes)

def parse_stl(file_path, languages_to_parse=['English']):
    """Parses the STL file and returns entries, stl_type, and language_names."""
    with open(file_path, 'rb') as f:
        # Read stl_type
        stl_type = read_bstr(f)
        print(f"stl_type: {stl_type}")

        # Read entry_count
        entry_count_bytes = f.read(4)
        if len(entry_count_bytes) < 4:
            print("Failed to read 4 bytes for entry_count.")
            return None, None, None
        entry_count = struct.unpack('<I', entry_count_bytes)[0]
        print(f"entry_count: {entry_count}")

        entries = []
        for _ in range(entry_count):
            string_id = read_bstr(f)
            entry_id_bytes = f.read(4)
            if len(entry_id_bytes) < 4:
                print("Failed to read 4 bytes for entry_id.")
                return None, None, None
            entry_id = struct.unpack('<I', entry_id_bytes)[0]
            entries.append({'string_id': string_id, 'id': entry_id})

        # Read language_count
        language_count_bytes = f.read(4)
        if len(language_count_bytes) < 4:
            print("Failed to read 4 bytes for language_count.")
            return None, None, None
        language_count = struct.unpack('<I', language_count_bytes)[0]
        print(f"language_count: {language_count}")

        # Map language indices to language names
        language_names = ['Korean', 'English', 'Japanese', 'Chinese_Simplified', 'Chinese_Traditional']
        if language_count > len(language_names):
            print("Warning: More languages in file than language names provided.")
            # Extend the list with generic names
            language_names.extend([f'Language_{i}' for i in range(len(language_names), language_count)])

        # Determine indices of languages to parse
        language_indices = [idx for idx, lang in enumerate(language_names) if lang in languages_to_parse]
        print(f"Languages to parse: {[language_names[idx] for idx in language_indices]}")

        # Read language_offsets
        language_offsets = []
        for _ in range(language_count):
            lang_offset_bytes = f.read(4)
            if len(lang_offset_bytes) < 4:
                print("Failed to read 4 bytes for language_offset.")
                return None, None, None
            language_offset = struct.unpack('<I', lang_offset_bytes)[0]
            language_offsets.append(language_offset)

        # Read entry_offsets for each language
        entry_offsets = []
        for lang_idx in language_indices:
            f.seek(language_offsets[lang_idx])
            offsets = []
            for entry_idx in range(entry_count):
                entry_offset_bytes = f.read(4)
                if len(entry_offset_bytes) < 4:
                    print(f"Failed to read 4 bytes for entry_offset at language {lang_idx}, entry {entry_idx}")
                    return None, None, None
                entry_offset = struct.unpack('<I', entry_offset_bytes)[0]
                offsets.append(entry_offset)
            entry_offsets.append(offsets)

        # Read the actual text data
        for idx, lang_idx in enumerate(language_indices):
            lang_name = language_names[lang_idx]
            offsets = entry_offsets[idx]
            for entry_idx in range(entry_count):
                entry_offset = offsets[entry_idx]
                f.seek(entry_offset)
                text = read_bstr(f)
                entries[entry_idx][f'text_{lang_name}'] = text

                if stl_type in ("QEST01", "ITST01"):
                    comment = read_bstr(f)
                    entries[entry_idx][f'comment_{lang_name}'] = comment

                    if stl_type == "QEST01":
                        quest1 = read_bstr(f)
                        quest2 = read_bstr(f)
                        entries[entry_idx][f'quest1_{lang_name}'] = quest1
                        entries[entry_idx][f'quest2_{lang_name}'] = quest2
    return entries, stl_type, language_names

def write_stl(file_path, entries, stl_type, language_names, languages_to_parse=['English']):
    """Writes the entries back to an STL file."""
    with open(file_path, 'wb') as f:
        # Write stl_type
        write_bstr(f, stl_type)

        # Write entry_count
        entry_count = len(entries)
        f.write(struct.pack('<I', entry_count))

        # Write Entries
        for entry in entries:
            write_bstr(f, entry['string_id'])
            f.write(struct.pack('<I', entry['id']))

        # Write language_count
        language_count = len(language_names)
        f.write(struct.pack('<I', language_count))

        # Prepare placeholders for language_offsets
        language_offsets_positions = f.tell()
        language_offsets = []
        for _ in range(language_count):
            # Write placeholder for language offset
            f.write(struct.pack('<I', 0))

        # Prepare to calculate language_offsets
        entry_offsets_list = []
        for lang_idx in range(language_count):
            entry_offsets = []
            entry_offsets_positions = f.tell()
            for _ in range(entry_count):
                # Write placeholder for entry offset
                f.write(struct.pack('<I', 0))
            entry_offsets_list.append((entry_offsets_positions, entry_offsets))

        # Now, write the text data and collect the offsets
        for lang_idx in range(language_count):
            lang_name = language_names[lang_idx]
            entry_offsets = []
            for entry_idx, entry in enumerate(entries):
                entry_offsets.append(f.tell())
                if lang_name in languages_to_parse:
                    text_col = f'text_{lang_name}'
                    comment_col = f'comment_{lang_name}'
                    # Write text
                    text = entry.get(text_col, '')
                    write_bstr(f, text)

                    if stl_type in ("QEST01", "ITST01"):
                        # Write comment
                        comment = entry.get(comment_col, '')
                        write_bstr(f, comment)

                        if stl_type == "QEST01":
                            # Write quest1 and quest2
                            quest1_col = f'quest1_{lang_name}'
                            quest2_col = f'quest2_{lang_name}'
                            quest1 = entry.get(quest1_col, '')
                            quest2 = entry.get(quest2_col, '')
                            write_bstr(f, quest1)
                            write_bstr(f, quest2)
                else:
                    # If not parsing this language, write empty strings
                    write_bstr(f, '')
                    if stl_type in ("QEST01", "ITST01"):
                        write_bstr(f, '')
                        if stl_type == "QEST01":
                            write_bstr(f, '')
                            write_bstr(f, '')
            # After writing all text data for this language, go back and write entry offsets
            current_pos = f.tell()
            # Write entry offsets
            f.seek(entry_offsets_list[lang_idx][0])
            for offset in entry_offsets:
                f.write(struct.pack('<I', offset))
            # Update language_offsets
            language_offsets.append(entry_offsets_list[lang_idx][0])
            # Return to current position
            f.seek(current_pos)

        # Now, go back and write language_offsets
        f.seek(language_offsets_positions)
        for offset in language_offsets:
            f.write(struct.pack('<I', offset))

def display_data_gui(df, stl_type, language_names, languages_to_parse=['English'], current_file_path=None, root=None):
    """Displays the data in a GUI window."""
    # Ensure DataFrame index is reset
    df.reset_index(drop=True, inplace=True)

    # Set window title
    if current_file_path:
        file_name = os.path.basename(current_file_path)
        root.title(f"STL Data Viewer - {file_name}")
    else:
        root.title("STL Data Viewer")

    root.geometry("1000x600")  # Increased width for better visibility

    # Function to save the STL file
    def save_stl_file():
        # Prompt the user to select a file path
        file_path = filedialog.asksaveasfilename(defaultextension=".stl", filetypes=[("STL files", "*.stl"), ("All files", "*.*")])
        if file_path:
            # Prepare entries data
            entries = df.to_dict('records')
            # Call the write_stl function
            write_stl(file_path, entries, stl_type, language_names, languages_to_parse)
            messagebox.showinfo("Save STL", f"STL file saved successfully at:\n{file_path}")

    # Function to open a new STL file
    def open_stl_file():
        new_file_path = filedialog.askopenfilename(title="Select STL File", filetypes=[("STL files", "*.stl"), ("All files", "*.*")])
        if new_file_path:
            # Parse the new STL file
            new_stl_data, new_stl_type, new_language_names = parse_stl(new_file_path, languages_to_parse)
            if new_stl_data is None:
                messagebox.showerror("Error", "Failed to parse the selected STL file.")
                return
            # Update the DataFrame and other variables
            nonlocal df, stl_type, language_names, current_file_path
            df = pd.DataFrame(new_stl_data)
            df.reset_index(drop=True, inplace=True)  # Reset index after loading new data
            stl_type = new_stl_type
            language_names = new_language_names
            current_file_path = new_file_path
            # Update the window title
            file_name = os.path.basename(current_file_path)
            root.title(f"STL Data Viewer - {file_name}")
            # Refresh the Treeview
            update_treeview(reset=True)
        else:
            messagebox.showinfo("No File Selected", "No STL file was selected.")

    # Function to export data to CSV
    def export_to_csv():
        csv_file_path = filedialog.asksaveasfilename(defaultextension=".csv", filetypes=[("CSV files", "*.csv"), ("All files", "*.*")])
        if csv_file_path:
            df.to_csv(csv_file_path, index=False)
            messagebox.showinfo("Export to CSV", f"Data exported successfully to:\n{csv_file_path}")

    # Create a menu bar
    menu_bar = tk.Menu(root)
    root.config(menu=menu_bar)

    # Add file menu
    file_menu = tk.Menu(menu_bar, tearoff=0)
    menu_bar.add_cascade(label="File", menu=file_menu)
    file_menu.add_command(label="Open", command=open_stl_file)
    file_menu.add_command(label="Save STL", command=save_stl_file)
    file_menu.add_command(label="Export to CSV", command=export_to_csv)
    file_menu.add_separator()
    file_menu.add_command(label="Exit", command=root.quit)

    # Create a frame for the search bar and Treeview
    top_frame = ttk.Frame(root)
    top_frame.pack(fill='x')

    # Create a frame for the Treeview
    frame = ttk.Frame(root)
    frame.pack(fill='both', expand=True)

    # Search bar
    search_var = tk.StringVar()
    search_entry = ttk.Entry(top_frame, textvariable=search_var)
    search_entry.pack(side='left', padx=5, pady=5, fill='x', expand=True)

    # Search button
    search_button = ttk.Button(top_frame, text="Search", command=lambda: update_treeview())
    search_button.pack(side='left', padx=5)

    # Reset button
    reset_button = ttk.Button(top_frame, text="Reset", command=lambda: update_treeview(reset=True))
    reset_button.pack(side='left', padx=5)

    # Filter DataFrame columns to include only the selected languages
    columns_to_display = ['string_id', 'id']
    for lang in languages_to_parse:
        text_col = f'text_{lang}'
        columns_to_display.append(text_col)
        comment_col = f'comment_{lang}'
        if comment_col in df.columns:
            columns_to_display.append(comment_col)
    df = df[columns_to_display]

    # Create the Treeview widget
    tree = ttk.Treeview(frame)
    tree.pack(side='left', fill='both', expand=True)

    # Define columns
    tree['columns'] = columns_to_display
    tree['show'] = 'headings'  # Hide the first empty column

    # Configure columns
    for col in columns_to_display:
        tree.heading(col, text=col)
        if col in ['string_id', 'id']:
            tree.column(col, anchor='w', width=100)
        else:
            tree.column(col, anchor='w', width=300)  # Adjusted width for better visibility

    # Add a scrollbar
    scrollbar = ttk.Scrollbar(frame, orient='vertical', command=tree.yview)
    tree.configure(yscroll=scrollbar.set)
    scrollbar.pack(side='right', fill='y')

    # Function to update the Treeview based on search
    def update_treeview(reset=False):
        # Ensure df index is reset
        df.reset_index(drop=True, inplace=True)

        # Clear the current content
        tree.delete(*tree.get_children())

        # Debug: Print the search input
        search_input = search_var.get()
        print(f"Search input before condition: '{search_input}'")

        # Decide which data to display
        if reset or not search_input.strip():
            display_df = df
            search_var.set('')
            print("Displaying all records.")
        else:
            search_text = search_input.lower()
            print(f"Searching for: '{search_text}'")
            # Filter rows where any column contains the search_text
            mask = df.apply(lambda row: row.astype(str).str.lower().str.contains(search_text).any(), axis=1)
            display_df = df[mask]
            print(f"Number of matching records: {display_df.shape[0]}")

        if display_df.empty:
            print("No matching records found.")
            messagebox.showinfo("Search Result", "No matching records found.")
            return

        # Insert data into the Treeview
        for index, row in display_df.iterrows():
            tree.insert("", "end", iid=index, values=list(row))

    # Function to handle double-click for editing
    def on_double_click(event):
        item_id = tree.focus()
        if not item_id:
            return
        item = tree.item(item_id)
        values = item['values']
        column = tree.identify_column(event.x)
        column_index = int(column.replace('#', '')) - 1
        column_name = columns_to_display[column_index]

        # Open edit dialog
        edit_window = tk.Toplevel(root)
        edit_window.title(f"Edit {column_name}")
        tk.Label(edit_window, text=f"Current Value:").pack(pady=5)
        current_value = values[column_index]

        # Create the Entry widget without StringVar
        text_entry = tk.Entry(edit_window, width=50)
        text_entry.pack(pady=5)
        # Insert the current value into the Entry widget
        text_entry.insert(0, current_value)

        def save_edit():
            new_value = text_entry.get()
            index = int(item_id)
            print(f"Saving edit: item_id={item_id}, index={index}, column_name={column_name}, new_value={new_value}")
            try:
                # Update the DataFrame
                df.at[index, column_name] = new_value
                # Update the Treeview
                tree.set(item_id, column=column_name, value=new_value)
                edit_window.destroy()
            except Exception as e:
                print(f"Error occurred: {e}")
                messagebox.showerror("Error", f"An error occurred while saving:\n{e}")
                edit_window.destroy()

        tk.Button(edit_window, text="Save", command=save_edit).pack(pady=5)

    # Bind the double-click event
    tree.bind("<Double-1>", on_double_click)

    # Initially populate the Treeview with all data
    update_treeview()

def main():
    # Create the main Tkinter window
    root = tk.Tk()
    root.withdraw()  # Hide the main window initially

    # Prompt the user to select an STL file
    file_path = filedialog.askopenfilename(title="Select STL File", filetypes=[("STL files", "*.stl"), ("All files", "*.*")])
    if not file_path:
        messagebox.showinfo("No File Selected", "No STL file was selected. Exiting the application.")
        root.destroy()
        exit()

    # Define which languages to parse
    languages_to_parse = ['English']  # Adjust this list as needed

    # Parse the STL file
    stl_data, stl_type, language_names = parse_stl(file_path, languages_to_parse)

    if stl_data is None:
        messagebox.showerror("Error", "Failed to parse the selected STL file.")
        root.destroy()
        exit()

    # Create a DataFrame
    df = pd.DataFrame(stl_data)

    # Optional: Print the first few rows for verification
    print("Initial DataFrame:")
    print(df.head())

    # Deiconify the main window and display the GUI
    root.deiconify()
    display_data_gui(df, stl_type, language_names, languages_to_parse, file_path, root)

    # Start the Tkinter event loop
    root.mainloop()

if __name__ == "__main__":
    main()
