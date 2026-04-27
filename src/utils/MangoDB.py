import sqlite3
from sqlite3 import Error
import configparser
import pandas as pd
import re
from typing import Any, Dict, Optional, Sequence, Tuple, Union

mongo_config = configparser.ConfigParser()
mongo_config.read('conf/mango.ini', encoding='utf-8')


class MangoDatabase:
    def __init__(self):
        """Initialize the database connection."""
        self.db_file = mongo_config.get('MangoDB', 'db_file')
        self.connection: Optional[sqlite3.Connection] = None
        try:
            self.connection = sqlite3.connect(self.db_file, check_same_thread=False)
            print(f"Connected to SQLite database: {self.db_file}")
        except Error as e:
            print(f"Failed to connect to SQLite database {self.db_file}: {e}")
            raise

    def insert_data(self, table: str, data: Sequence[Any]) -> bool:
        """Insert a row of data into the table."""
        placeholders = ', '.join(['?'] * len(data))
        # 表名可能以数字开头（如 24MM_TTS），需要使用双引号包裹以避免 SQLite 语法错误
        sql = f'INSERT OR REPLACE INTO "{table}" VALUES ({placeholders})'
        result = self.execute_sql(sql, data)
        if result:
            print(f"Data inserted successfully into {table}: {data}")
            return True
        print(f"Data insert failed into {table}: {data}")
        return False
    
    def insert_excel(self) -> None:
        # Create a table
        parent_prefix = 'MangoDB.'
        sub_sections = [
            section for section in mongo_config.sections() 
            if section.startswith(parent_prefix)
        ]
        for section in sub_sections:
            support_title_cmn = mongo_config.get(section, 'support_title_cmn').split(",")
            support_title_eng = mongo_config.get(section, 'support_title_eng').split(",")
            columns_title = ["id TEXT PRIMARY KEY", "skill TEXT NOT NULL"]
            support_titles = support_title_cmn + support_title_eng
            support_titles = list(dict.fromkeys(support_titles))
            for title in support_titles:
                columns_title.append(f"{title} TEXT")
            table_name = mongo_config.get(section, 'db_table')
            # 同样对表名加引号，避免以数字开头导致的 "unrecognized token" 错误
            create_table_sql = f'''CREATE TABLE IF NOT EXISTS "{table_name}" (
                                    {', '.join(columns_title)}
                                );'''

            self.execute_sql(create_table_sql)

            # 读取Excel文件
            xls = pd.ExcelFile(mongo_config.get(section, 'tts'), engine='openpyxl')
            for sheet_name in xls.sheet_names:
                df = pd.read_excel(xls, sheet_name=sheet_name, dtype=str)
                # 遍历每一行数据
                for index, row in df.iterrows():
                    # 提取序号、sheet名和TTS文言
                    serial_id = row['序号']
                    output = (str(serial_id).strip(),
                              sheet_name
                              )
                    for title in support_titles:
                        value = row.get(title, "")
                        title_params = re.sub(r'【.*?】', '*', str(value))
                        if title.endswith("_ENG"):
                            parser_title = str(title_params).replace('\r\n', '\n').replace('\n', '|')
                        else:
                            parser_title = str(title_params).replace(' ', '').replace('\r\n', '\n').replace('\n', '|')
                        output += (parser_title,)
                    # 构造输出格式
                    # 打印输出（或根据需要保存到文件或进行其他处理）
                    self.insert_data(mongo_config.get(section, 'db_table'), output)


    def update_data(
        self,
        table: str,
        data: Dict[str, Any],
        condition: str,
        condition_value: Union[Any, Sequence[Any]],
    ) -> bool:
        """Update a row in the table with the specified condition."""
        set_clause = ', '.join([f"{key} = ?" for key in data.keys()])
        sql = f'UPDATE "{table}" SET {set_clause} WHERE {condition}'
        if isinstance(condition_value, (tuple, list)):
            values = tuple(data.values()) + tuple(condition_value)
        else:
            values = tuple(data.values()) + (condition_value,)
        result = self.execute_sql(sql, values)
        if result:
            print(f"Data updated successfully in {table}: {data}")
            return True
        print(f"Data update failed in {table}: {data}")
        return False

    def delete_data(self, table: str, condition: str, condition_value: Any) -> bool:
        """Delete a row from the table with the specified condition."""
        sql = f'DELETE FROM {table} WHERE {condition} = ?'
        try:
            cursor = self.connection.cursor()
            cursor.execute(sql, (condition_value,))
            self.connection.commit()
            print(f"Data deleted successfully from {table} where {condition} = {condition_value}")
            return True
        except Error as e:
            print(f"Data delete failed from {table} where {condition} = {condition_value}: {e}")
            return False

    def query_data(self, table: str, columns: str = '*', condition: Optional[str] = None, condition_value: Any = None) -> Optional[Tuple[Any, ...]]:
        """Query data from the table with the specified condition."""
        if condition:
            sql = f'SELECT {columns} FROM "{table}" WHERE {condition} = ?'
            if isinstance(condition_value, (tuple, list)):
                params: Optional[Union[Tuple[Any, ...], Sequence[Any]]] = tuple(condition_value)
            else:
                params = (condition_value,)
        else:
            sql = f'SELECT {columns} FROM "{table}"'
            params = None
        result = self.execute_sql(sql, params)
        if not result:
            return None
        row = result.fetchone()
        return row if row is not None else None

    def execute_sql(self, sql: str, params: Optional[Union[Sequence[Any], Dict[str, Any], Any]] = None):
        """Execute a SQL statement."""
        if not self.connection:
            print("Database connection is not initialized.")
            return None

        cursor = self.connection.cursor()
        try:
            if params is None:
                cursor.execute(sql)
            elif isinstance(params, (list, tuple, dict)):
                cursor.execute(sql, params)
            else:
                cursor.execute(sql, (params,))
            self.connection.commit()
            return cursor
        except Error as e:
            print(f"Failed to execute SQL: {sql}, params: {params}, error: {e}")
            return None

    def close_connection(self):
        """Close the database connection."""
        if self.connection:
            self.connection.close()
            print("The connection is closed")

# Example usage:
if __name__ == '__main__':
    database = MangoDatabase()
    database.insert_excel()
    # print(database.query_data(table='TTS', condition="id", condition_value="GSGMKG-09"))
    # Close connection
    database.close_connection()
