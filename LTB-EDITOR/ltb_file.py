import struct
from typing import List, Optional
import openai
import os
from dotenv import load_dotenv
import logging
import time

# Load environment variables from .env file
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class LTBFile:
    def __init__(self, encoding='utf-16le'):
        self.rows: int = 0
        self.columns: int = 0
        self.cells: List[tuple] = []  # List of tuples: (offset, size)
        self.data_offset: int = 0
        self.data: bytes = b''  # Raw data bytes
        self.encoding = encoding

    def get_string(self, row: int, column: int) -> Optional[str]:
        index = row * self.columns + column
        if index >= len(self.cells):
            return None
        offset, size = self.cells[index]
        if offset < self.data_offset or size == 0:
            return None
        start = offset - self.data_offset
        if self.encoding.lower() == 'utf-16le':
            end = start + size * 2  # Each UTF-16 code unit is 2 bytes
        elif self.encoding.lower() == 'euc-kr':
            end = start + size  # Each euc-kr character is 1 byte
        else:
            raise ValueError(f"Unsupported encoding: {self.encoding}")

        try:
            string_bytes = self.data[start:end]
            string = string_bytes.decode(self.encoding).rstrip('\x00')
            return string
        except (IndexError, UnicodeDecodeError) as e:
            logger.error(f"Error decoding string at row {row}, column {column}: {e}")
            return None

    def set_string(self, row: int, column: int, value: str):
        index = row * self.columns + column
        if index >= len(self.cells):
            raise IndexError("Row or column out of range.")
        # Updating the string requires rebuilding the entire data section
        # This will be handled during the save operation
        pass  # No action needed here

    @staticmethod
    def read(file_path: str, encoding='utf-16le') -> 'LTBFile':
        ltb = LTBFile(encoding=encoding)
        with open(file_path, 'rb') as f:
            # Read header
            header = f.read(8)
            if len(header) < 8:
                raise ValueError("File too short to contain valid header.")
            ltb.columns, ltb.rows = struct.unpack('<II', header)
            logger.info(f"Columns: {ltb.columns}, Rows: {ltb.rows}")

            # Read cell definitions
            for _ in range(ltb.rows * ltb.columns):
                cell_data = f.read(6)  # 4 bytes offset, 2 bytes size
                if len(cell_data) < 6:
                    raise ValueError("File too short to contain all cell definitions.")
                offset, size = struct.unpack('<IH', cell_data)
                ltb.cells.append((offset, size))
            ltb.data_offset = f.tell()
            logger.info(f"Data Offset: {ltb.data_offset}")

            # Read data section
            ltb.data = f.read()
            logger.info(f"Data length (bytes): {len(ltb.data)}")

        return ltb

    def write_with_update(self, file_path: str, edited_table: List[List[str]], selected_columns: List[int]):
        with open(file_path, 'wb') as f:
            # Write header
            f.write(struct.pack('<II', self.columns, self.rows))

            # Placeholder for cell definitions
            cell_definitions = [(0, 0) for _ in range(self.rows * self.columns)]
            # Write placeholders
            for cell in cell_definitions:
                f.write(struct.pack('<IH', cell[0], cell[1]))

            # Record new data_offset
            new_data_offset = f.tell()

            # Initialize temporary variables
            temp_new_data = bytearray()
            temp_new_cells = []
            current_offset = 0

            for row_index in range(self.rows):
                for col_index in range(self.columns):
                    if col_index in selected_columns:
                        # Get the edited string
                        edited_string = edited_table[row_index][selected_columns.index(col_index)]
                        if not isinstance(edited_string, str):
                            edited_string = str(edited_string)

                        if self.encoding.lower() == 'utf-16le':
                            encoded = edited_string.encode(self.encoding) + b'\x00\x00'  # Null-terminated
                            size = len(encoded) // 2
                        elif self.encoding.lower() == 'euc-kr':
                            encoded = edited_string.encode(self.encoding) + b'\x00'  # Null-terminated
                            size = len(encoded)
                        else:
                            raise ValueError(f"Unsupported encoding: {self.encoding}")
                    else:
                        # Retain the original string
                        original_string = self.get_string(row_index, col_index)
                        if not isinstance(original_string, str):
                            original_string = str(original_string)

                        if self.encoding.lower() == 'utf-16le':
                            encoded = original_string.encode(self.encoding) + b'\x00\x00'  # Null-terminated
                            size = len(encoded) // 2
                        elif self.encoding.lower() == 'euc-kr':
                            encoded = original_string.encode(self.encoding) + b'\x00'  # Null-terminated
                            size = len(encoded)
                        else:
                            raise ValueError(f"Unsupported encoding: {self.encoding}")

                    # Update cells with new offsets and sizes
                    temp_new_cells.append((new_data_offset + current_offset, size))
                    temp_new_data += encoded
                    current_offset += len(encoded)

            # Write data section
            f.write(temp_new_data)

            # Now, go back and write the correct cell definitions
            f.seek(8)  # After header
            for cell in temp_new_cells:
                f.write(struct.pack('<IH', cell[0], cell[1]))

            # Update self.cells and self.data
            self.cells = temp_new_cells
            self.data = bytes(temp_new_data)

    def to_string_table(self, selected_columns: List[int]) -> List[List[str]]:
        """
        Converts the LTBFile data into a list of lists of strings,
        selecting only the specified columns.

        Args:
            selected_columns (List[int]): List of column indices to include.

        Returns:
            List[List[str]]: Table data as a list of rows, each row is a list of strings.
        """
        table = []
        for row in range(self.rows):
            row_data = []
            for col in selected_columns:
                string = self.get_string(row, col)
                row_data.append(string if string is not None else "")
            table.append(row_data)
        return table

    def generate_dialogue(self, npc_role: str, npc_name: str, context: Optional[str] = None,
                          use_assistant: bool = False) -> Optional[str]:
        """
        Generates a dialogue line for an NPC based on their role and name.
        Args:
            npc_role: The role of the NPC
            npc_name: The name of the NPC
            context: Optional context for the dialogue
            use_assistant: If True, uses the custom assistant; if False, uses GPT-4
        """
        client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        if not client.api_key:
            logger.error("OpenAI API key not found. Please set it in the .env file.")
            return None

        # Define the prompt based on NPC role
        prompt = f"You are a role-playing game character named {npc_name}, who is a {npc_role} in the world of Rose Online."
        if context:
            prompt += f" Context: {context}"
        prompt += " Generate an engaging dialogue line appropriate for your role."

        try:
            max_retries = 5
            backoff_factor = 0.5

            for attempt in range(max_retries):
                try:
                    if use_assistant:
                        # Use the custom assistant
                        thread = client.beta.threads.create()
                        message = client.beta.threads.messages.create(
                            thread_id=thread.id,
                            role="user",
                            content=prompt
                        )
                        run = client.beta.threads.runs.create(
                            thread_id=thread.id,
                            assistant_id="asst_EqgqfB5HpggNuKyq0rqcEUL4"
                        )

                        # Wait for completion
                        while True:
                            run_status = client.beta.threads.runs.retrieve(
                                thread_id=thread.id,
                                run_id=run.id
                            )
                            if run_status.status == 'completed':
                                messages = client.beta.threads.messages.list(thread_id=thread.id)
                                dialogue = messages.data[0].content[0].text.value.strip()
                                break
                            elif run_status.status in ['failed', 'cancelled', 'expired']:
                                raise Exception(f"Assistant run failed with status: {run_status.status}")
                            time.sleep(1)
                    else:
                        # Use GPT-4
                        response = client.chat.completions.create(
                            model="gpt-4o",
                            messages=[
                                {"role": "system", "content": "You are a helpful assistant."},
                                {"role": "user", "content": prompt}
                            ],
                            max_tokens=60,
                            n=1,
                            stop=None,
                            temperature=0.7,
                        )
                        dialogue = response.choices[0].message.content.strip()

                    logger.info(f"Generated dialogue for {npc_name} ({npc_role}): {dialogue}")
                    return dialogue

                except openai.OpenAIError as e:
                    wait = backoff_factor * (2 ** attempt)
                    logger.warning(f"OpenAI API error. Retrying in {wait} seconds... Error: {e}")
                    time.sleep(wait)
                except Exception as e:
                    logger.error(f"Unexpected error: {e}")
                    return None

            logger.error("Max retries exceeded. Failed to generate dialogue.")
            return None

        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            return None