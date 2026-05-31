import os
import pandas as pd
import time

def detect_delimiter(filename, num_lines=10, possible_delimiters=[',', ';', '\t', '|', ':', ' ']):
    try:
        with open(filename, 'r', encoding='utf-8') as file:
            lines = [file.readline() for _ in range(num_lines) if file.readline()]
    except UnicodeDecodeError:
        try:
            with open(filename, 'r', encoding='cp1251') as file:
                lines = [file.readline() for _ in range(num_lines) if file.readline()]
        except:
            with open(filename, 'r', encoding='latin-1') as file:
                lines = [file.readline() for _ in range(num_lines) if file.readline()]

    if not lines:
        return ',', 'utf-8'

    delimiter_counts = {}
    for delimiter in possible_delimiters:
        counts = []
        for line in lines:
            parts = line.split(delimiter)
            if len(parts) > 1:
                counts.append(len(parts))

        if counts:
            counts.sort()
            median_idx = len(counts) // 2
            median_count = counts[median_idx]
            stability = sum(1 for c in counts if c == median_count) / len(counts)
            delimiter_counts[delimiter] = {
                'median': median_count,
                'stability': stability,
                'max': max(counts)
            }

    if not delimiter_counts:
        return ',', 'utf-8'

    best_delimiter = max(
        delimiter_counts.keys(),
        key=lambda d: (delimiter_counts[d]['stability'], delimiter_counts[d]['median'])
    )

    print(f"Определен разделитель: '{best_delimiter}'")
    return best_delimiter

def read_csv_auto_delimiter(filename, max_rows=None):
    start_time = time.time()
    print(f"\nЧтение CSV файла: {os.path.basename(filename)}")
    delimiter = detect_delimiter(filename)

    encodings = ['utf-8', 'cp1251', 'latin-1', 'windows-1251']

    for encoding in encodings:
        try:
            if max_rows:
                df = pd.read_csv(filename, sep=delimiter, encoding=encoding,
                                 decimal=',', nrows=max_rows, low_memory=False)
            else:
                sample_size = 100000 if os.path.getsize(filename) > 100 * 1024 * 1024 else None
                if sample_size:
                    df = pd.read_csv(filename, sep=delimiter, encoding=encoding,
                                     decimal=',', nrows=sample_size, low_memory=False)
                else:
                    df = pd.read_csv(filename, sep=delimiter, encoding=encoding,
                                     decimal=',', low_memory=False)

            print(f"✓ Успешно! Размер: {df.shape[0]} строк, {df.shape[1]} столбцов")
            print(f"  Время чтения: {time.time() - start_time:.1f} сек")
            return df, delimiter, encoding

        except UnicodeDecodeError:
            continue
        except pd.errors.ParserError:
            continue
        except Exception as e:
            continue

    raise ValueError(f"Не удалось прочитать файл {filename} ни с одной кодировкой")

def read_file_auto(filename, max_rows=None):
    ext = os.path.splitext(filename)[1].lower()

    if ext == '.csv':
        return read_csv_auto_delimiter(filename, max_rows)

    elif ext in ('.xls', '.xlsx'):
        try:
            print(f"\nЧтение Excel файла: {os.path.basename(filename)}")
            if max_rows:
                df = pd.read_excel(filename, nrows=max_rows)
            else:
                df = pd.read_excel(filename)
            print(f"✓ Успешно загружено {df.shape[0]} строк, {df.shape[1]} столбцов")
            return df, None, None
        except Exception as e:
            raise ValueError(f"Ошибка чтения Excel файла: {e}")

    elif ext == '.ods':
        try:
            print(f"\nЧтение ODS файла: {os.path.basename(filename)}")
            if max_rows:
                df = pd.read_excel(filename, engine='odf', nrows=max_rows)
            else:
                df = pd.read_excel(filename, engine='odf')
            print(f"✓ Успешно загружено {df.shape[0]} строк, {df.shape[1]} столбцов")
            return df, None, None
        except ImportError:
            raise ImportError("Для чтения ODS файлов требуется библиотека odfpy. Установите: pip install odfpy")
        except Exception as e:
            raise ValueError(f"Ошибка чтения ODS файла: {e}")

    else:
        raise ValueError(f"Неподдерживаемый формат файла: {ext}")

def analyze_file_structure(filename):
    ext = os.path.splitext(filename)[1].lower()

    if ext == '.csv':
        print(f"\nАнализ CSV файла: {filename}")
        encodings = ['utf-8', 'cp1251', 'latin-1', 'windows-1251']
        for encoding in encodings:
            try:
                with open(filename, 'r', encoding=encoding) as f:
                    lines = []
                    for i in range(5):
                        line = f.readline()
                        if not line:
                            break
                        lines.append(line.rstrip('\n'))
                print(f"Кодировка {encoding}:")
                for i, line in enumerate(lines):
                    print(f"  Строка {i+1}: {repr(line[:100])}")
                if lines:
                    print("Анализ разделителей в первой строке:")
                    delimiters = [',', ';', '\t', '|', ':', ' ']
                    for delim in delimiters:
                        parts = lines[0].split(delim)
                        if len(parts) > 1:
                            print(f"  '{delim}': {len(parts)} частей")
                return encoding
            except UnicodeDecodeError:
                continue
        print("Не удалось определить кодировку")
        return None

    else:
        try:
            if ext in ('.xls', '.xlsx'):
                df_sample = pd.read_excel(filename, nrows=5)
                print(f"\nАнализ Excel файла: {filename}")
                print("Первые 5 строк:")
                print(df_sample.to_string())
                xl = pd.ExcelFile(filename)
                print(f"Доступные листы: {xl.sheet_names}")
            elif ext == '.ods':
                df_sample = pd.read_excel(filename, engine='odf', nrows=5)
                print(f"\nАнализ ODS файла: {filename}")
                print("Первые 5 строк:")
                print(df_sample.to_string())
            else:
                print("Неподдерживаемый формат")
                return None
            return 'utf-8'
        except Exception as e:
            print(f"Ошибка анализа: {e}")
            return None