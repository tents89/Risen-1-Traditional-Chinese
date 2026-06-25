"""
Created by AI.
Risen 1, 2 & 3 string-table reader / writer.

Formats:
    Risen 1 (TAB0):
        header  : "TAB0" (4B) + int16 version + int16 format + int64 dateTime
        string  : uint16 charCount + charCount * 2 bytes (Always UTF-16 LE)
    
    Risen 2 (TAB1):
        header  : "TAB1" (4B) + uint16 version (=2) + uint16 isUnicode + uint64 fileTime
        string  : uint16 charCount + charCount * N bytes (N=2 if isUnicode else 1)

    Risen 3 (GAR5/STB5/STB6, e.g. w_strings.bin):
        GAR5 wrapper followed by STB string-table data. Text is stored as rows keyed by
        sorted DJB2 IDs, with each column using compressed UTF-16 symbol sequences.

Usage:
    # Extract (Risen 1/2 .tab or Risen 3 w_strings.bin auto-detected)
    python risen_text.py extract <file_or_dir> [-o out_dir] [-f csv|json|txt] [--id-map id_map.csv]

    # Pack back to .tab / .bin (--game is REQUIRED)
    # Note: Risen 3 (-g 3) requires an original template file via --template
    python risen_text.py pack    <file_or_dir> -g {1,2,3} [-o out_dir] [--template w_strings.bin] [--id-map id_map.csv]
"""

import argparse
import csv
import json
import struct
import sys
import time
from pathlib import Path


# ---------- low-level IO ----------

def _read_exact(f, n):
    b = f.read(n)
    if len(b) != n:
        raise EOFError(f"short read at {f.tell()}: wanted {n}, got {len(b)}")
    return b


def _ru8(f):  return _read_exact(f, 1)[0]
def _ru16(f): return struct.unpack("<H", _read_exact(f, 2))[0]
def _ri16(f): return struct.unpack("<h", _read_exact(f, 2))[0]
def _ru32(f): return struct.unpack("<I", _read_exact(f, 4))[0]
def _ri32(f): return struct.unpack("<i", _read_exact(f, 4))[0]
def _ri64(f): return struct.unpack("<q", _read_exact(f, 8))[0]
def _ru64(f): return struct.unpack("<Q", _read_exact(f, 8))[0]


def _rstr(f, is_unicode=True):
    n = _ru16(f)
    if is_unicode:
        return _read_exact(f, n * 2).decode("utf-16-le", errors="replace")
    return _read_exact(f, n).decode("latin-1", errors="replace")


def _wstr(buf, s, is_unicode=True):
    if is_unicode:
        data = s.encode("utf-16-le")
        n_units = len(data) // 2
        if n_units > 0xFFFF:
            raise ValueError(f"String too long ({n_units} code units, max 65535): {s[:40]!r}...")
        buf += struct.pack("<H", n_units)
        buf += data
    else:
        data = s.encode("latin-1", errors="replace")
        if len(data) > 0xFFFF:
            raise ValueError(f"String too long ({len(data)} bytes, max 65535): {s[:40]!r}...")
        buf += struct.pack("<H", len(data))
        buf += data


# ---------- core ----------

def read_tab(path):
    with open(path, "rb") as f:
        magic = _read_exact(f, 4)
        if magic == b"TAB0":
            game = 1
            version = _ri16(f)
            fmt = _ri16(f)
            date_time = _ri64(f)
            is_unicode = True
        elif magic == b"TAB1":
            game = 2
            version = _ru16(f)
            if version != 2:
                raise ValueError(f"{path}: unknown Risen 2 .tab version {version}, expected 2")
            is_unicode = max(_ru16(f), 1)
            date_time = _ru64(f)
            fmt = 1
        else:
            raise ValueError(f"{path}: bad magic {magic!r}, expected b'TAB0' or b'TAB1'")

        col_count = _ru32(f)
        headers, columns = [], []
        
        for _ in range(col_count):
            flag = _ru8(f)
            if flag == 0:
                continue
            _reserved = _ru16(f)
            name = _rstr(f, is_unicode)
            rows = _ru32(f)
            columns.append([_rstr(f, is_unicode) for _ in range(rows)])
            headers.append(name)

    return {
        "game": game,
        "version": version,
        "format": fmt,
        "is_unicode": is_unicode,
        "date_time": date_time,
        "headers": headers,
        "columns": columns,
    }


def _u32_at(data, offset, endian="<"):
    return struct.unpack_from(endian + "I", data, offset)[0]


def _i32_at(data, offset, endian="<"):
    return struct.unpack_from(endian + "i", data, offset)[0]


def _check_range(data, offset, size, label):
    if offset < 0 or size < 0 or offset + size > len(data):
        raise ValueError(f"{label}: invalid range offset={offset} size={size} file_size={len(data)}")


def _decode_cstring(data, offset, size, encoding="utf-8"):
    _check_range(data, offset, size, "string")
    raw = data[offset:offset + size]
    if raw.endswith(b"\0"):
        raw = raw[:-1]
    return raw.decode(encoding, errors="replace")


def genome_string_id_hash(text):
    value = 5381
    normalized = text.lower().replace("\\", "/")
    for char in normalized:
        value = ((value * 33) + ord(char)) & 0xFFFFFFFF
    return value


def default_risen3_id_map_path():
    path = Path(__file__).resolve().parent / "lianzifu-unpack.risen3.csv"
    return path if path.is_file() else None


def load_risen3_id_map(path):
    id_map = {}
    with open(path, "r", encoding="utf-8-sig", newline="") as fh:
        for line in fh:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            full_id, sep, rest = line.partition("|")
            if not sep:
                continue
            listed_hash = rest.split("|", 1)[0].strip()
            try:
                hashed = int(listed_hash, 16)
            except ValueError:
                raw_id = full_id.split(":", 1)[1] if ":" in full_id else full_id
                hashed = genome_string_id_hash(raw_id)
            id_map.setdefault(hashed, full_id)
    return id_map


def load_risen3_id_hash_map(path):
    id_hash_map = {}
    with open(path, "r", encoding="utf-8-sig", newline="") as fh:
        for line in fh:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            full_id, sep, rest = line.partition("|")
            if not sep:
                continue
            listed_hash = rest.split("|", 1)[0].strip()
            try:
                hashed = int(listed_hash, 16) & 0xFFFFFFFF
            except ValueError:
                raw_id = full_id.split(":", 1)[1] if ":" in full_id else full_id
                hashed = genome_string_id_hash(raw_id)
            raw_id = full_id.split(":", 1)[1] if ":" in full_id else full_id
            id_hash_map.setdefault(full_id, hashed)
            id_hash_map.setdefault(raw_id, hashed)
    return id_hash_map


def apply_risen3_id_map(tab, id_map):
    if tab.get("game") != 3 or not id_map or not tab.get("columns"):
        return 0

    changed = 0
    mapped = []
    for value in tab["columns"][0]:
        try:
            hashed = int(value, 16)
        except ValueError:
            mapped.append(value)
            continue
        if hashed in id_map:
            mapped.append(id_map[hashed])
            changed += 1
        else:
            mapped.append(value)
    tab["columns"][0] = mapped
    return changed


def read_stb(path):
    data = Path(path).read_bytes()
    if data.startswith(b"GAR5"):
        flags = data[4:8]
        if flags[:1] == b"\x20":
            endian = "<"
        elif flags[:1] == b"\x10":
            endian = ">"
        else:
            raise ValueError(f"{path}: unsupported GAR5 endian flags {flags.hex()}")
        stb_offset = 8
    else:
        endian = "<"
        stb_offset = 0

    _check_range(data, stb_offset, 36, "stb header")
    if data[stb_offset:stb_offset + 3] != b"STB":
        raise ValueError(f"{path}: bad Risen 3 STB magic at offset {stb_offset}")

    version = data[stb_offset + 3]
    source_count = _u32_at(data, stb_offset + 4, endian)
    reserved = _u32_at(data, stb_offset + 8, endian)
    column_count = _u32_at(data, stb_offset + 12, endian)
    row_count = _u32_at(data, stb_offset + 16, endian)
    source_table_offset = _u32_at(data, stb_offset + 20, endian)
    column_names_offset = _u32_at(data, stb_offset + 24, endian)
    column_table_offset = _u32_at(data, stb_offset + 28, endian)
    id_table_offset = _u32_at(data, stb_offset + 32, endian)

    if version not in (5, 6):
        raise ValueError(f"{path}: unknown STB version {version}, expected 5 or 6")
    if reserved != 0:
        raise ValueError(f"{path}: unexpected STB reserved value {reserved}")

    sources = []
    pos = source_table_offset
    for _ in range(source_count):
        _check_range(data, pos, 2, "source filepath length")
        length = struct.unpack_from(endian + "H", data, pos)[0]
        pos += 2
        _check_range(data, pos, length + 8, "source record")
        filepath = data[pos:pos + length].decode("utf-8", errors="replace")
        pos += length
        filetime_hi = _u32_at(data, pos, endian)
        filetime_lo = _u32_at(data, pos + 4, endian)
        pos += 8
        sources.append({
            "filepath": filepath,
            "filetime_hi": filetime_hi,
            "filetime_lo": filetime_lo,
        })

    _check_range(data, id_table_offset, 8, "id table")
    id_table_size = _u32_at(data, id_table_offset, endian)
    id_data_offset = _u32_at(data, id_table_offset + 4, endian)
    if id_table_size != row_count * 4:
        raise ValueError(f"{path}: id table size {id_table_size}, expected {row_count * 4}")
    _check_range(data, id_data_offset, id_table_size, "id data")
    ids = [
        _u32_at(data, id_data_offset + i * 4, endian)
        for i in range(row_count)
    ]

    _check_range(data, column_names_offset, column_count * 8, "column names table")
    headers = ["ID", "Hash"]
    for i in range(column_count):
        size = _u32_at(data, column_names_offset + i * 8, endian)
        offset = _u32_at(data, column_names_offset + i * 8 + 4, endian)
        headers.append(_decode_cstring(data, offset, size))

    _check_range(data, column_table_offset, column_count * 16, "column table")
    columns = [[f"0x{value:08X}" for value in ids], [f"{value:08x}" for value in ids]]
    for col_index in range(column_count):
        base = column_table_offset + col_index * 16
        string_table_size = _u32_at(data, base, endian)
        string_table_offset = _u32_at(data, base + 4, endian)
        symbol_table_size = _u32_at(data, base + 8, endian)
        symbol_table_offset = _u32_at(data, base + 12, endian)
        _check_range(data, string_table_offset, string_table_size, f"string table {col_index}")
        _check_range(data, symbol_table_offset, symbol_table_size, f"symbol table {col_index}")

        seq_base = string_table_offset + row_count * 4
        seq_end = string_table_offset + string_table_size
        symbol_count = symbol_table_size // 4
        symbol_cache = {0: b""}

        def decode_symbol(symbol_index):
            if symbol_index in symbol_cache:
                return symbol_cache[symbol_index]
            if symbol_index < 0 or symbol_index >= symbol_count:
                raise ValueError(
                    f"{path}: symbol index {symbol_index} out of range in column {col_index}"
                )

            stack = []
            seen = set()
            current = symbol_index
            while current and current not in symbol_cache:
                if current in seen:
                    raise ValueError(f"{path}: cyclic symbol chain in column {col_index}")
                seen.add(current)
                value = _u32_at(data, symbol_table_offset + current * 4, endian)
                prev = value & 0xFFFF
                code_unit = value >> 16
                stack.append((current, prev, code_unit))
                current = prev

            prefix = symbol_cache.get(current, b"")
            for idx, _prev, code_unit in reversed(stack):
                prefix = prefix + struct.pack("<H", code_unit)
                symbol_cache[idx] = prefix
            return symbol_cache[symbol_index]

        decoded = []
        for row in range(row_count):
            seq_start = _i32_at(data, string_table_offset + row * 4, endian)
            if seq_start < 0:
                decoded.append("")
                continue

            pos = seq_base + seq_start * 2
            if pos < seq_base or pos >= seq_end:
                raise ValueError(
                    f"{path}: sequence start {seq_start} out of range in column {col_index}, row {row}"
                )

            parts = []
            while True:
                _check_range(data, pos, 2, f"sequence column {col_index} row {row}")
                symbol_index = struct.unpack_from(endian + "H", data, pos)[0]
                pos += 2
                if symbol_index == 0:
                    break
                parts.append(decode_symbol(symbol_index))
                if pos > seq_end:
                    raise ValueError(f"{path}: unterminated sequence in column {col_index}, row {row}")

            decoded.append(b"".join(parts).decode("utf-16-le", errors="replace"))
        columns.append(decoded)

    return {
        "game": 3,
        "version": version,
        "format": "STB",
        "sources": sources,
        "headers": headers,
        "columns": columns,
    }


def read_string_table(path):
    with open(path, "rb") as f:
        magic = f.read(4)
    if magic in (b"TAB0", b"TAB1"):
        return read_tab(path)
    if magic == b"GAR5" or magic[:3] == b"STB":
        return read_stb(path)
    raise ValueError(f"{path}: unsupported string-table magic {magic!r}")


def parse_risen3_id(value, id_hash_map=None):
    text = str(value).strip()
    if text.lower().startswith("0x"):
        return int(text, 16) & 0xFFFFFFFF
    if id_hash_map and text in id_hash_map:
        return id_hash_map[text]
    raw_id = text.split(":", 1)[1] if ":" in text else text
    if id_hash_map and raw_id in id_hash_map:
        return id_hash_map[raw_id]
    return genome_string_id_hash(raw_id)


def _pack_u16(value, endian="<"):
    return struct.pack(endian + "H", value)


def _pack_u32(value, endian="<"):
    return struct.pack(endian + "I", value & 0xFFFFFFFF)


def _pack_i32(value, endian="<"):
    return struct.pack(endian + "i", value)


def _utf16_code_units(text):
    data = str(text).encode("utf-16-le", errors="surrogatepass")
    return struct.unpack("<" + "H" * (len(data) // 2), data) if data else ()


def _build_risen3_column(texts, endian="<"):
    starts = []
    sequences = bytearray()
    symbols = [0]
    symbol_index = {}
    symbol_length = [0]

    def add_symbol(prev, unit):
        if len(symbols) >= 0x10000:
            return None
        key = (prev, unit)
        index = symbol_index.get(key)
        if index is not None:
            return index
        index = len(symbols)
        symbol_index[key] = index
        symbols.append((unit << 16) | prev)
        symbol_length.append(symbol_length[prev] + 1)
        return index

    all_units = []
    seen_units = set()
    for text in texts:
        for unit in _utf16_code_units(text):
            if unit not in seen_units:
                seen_units.add(unit)
                all_units.append(unit)
    if len(all_units) >= 0x10000:
        raise ValueError("Risen 3 column contains too many distinct UTF-16 code units")
    for unit in all_units:
        add_symbol(0, unit)

    def single_symbol(unit):
        return symbol_index[(0, unit)]

    for text in texts:
        units = _utf16_code_units(text)
        if not units:
            starts.append(-1)
            continue

        starts.append(len(sequences) // 2)

        current = single_symbol(units[0])
        for unit in units[1:]:
            key = (current, unit)
            next_index = symbol_index.get(key)
            if next_index is not None:
                current = next_index
                continue

            sequences += _pack_u16(current, endian)
            if symbol_length[current] < 33:
                add_symbol(current, unit)
            current = single_symbol(unit)

        sequences += _pack_u16(current, endian)
        sequences += _pack_u16(0, endian)

    string_table = bytearray()
    for start in starts:
        string_table += _pack_i32(start, endian)
    string_table += sequences

    symbol_table = bytearray()
    for symbol in symbols:
        symbol_table += _pack_u32(symbol, endian)

    return bytes(string_table), bytes(symbol_table)


def write_risen3_bin(path, tab, template_path, id_hash_map=None):
    template = Path(template_path).read_bytes()
    if not template.startswith(b"GAR5"):
        raise ValueError(f"{template_path}: expected GAR5 Risen 3 template")

    flags = template[4:8]
    if flags[:1] == b"\x20":
        endian = "<"
    elif flags[:1] == b"\x10":
        endian = ">"
    else:
        raise ValueError(f"{template_path}: unsupported GAR5 endian flags {flags.hex()}")

    stb_offset = 8
    if template[stb_offset:stb_offset + 3] != b"STB":
        raise ValueError(f"{template_path}: bad STB magic")

    version = template[stb_offset + 3]
    source_count = _u32_at(template, stb_offset + 4, endian)
    reserved = _u32_at(template, stb_offset + 8, endian)
    column_count = _u32_at(template, stb_offset + 12, endian)
    source_table_offset = _u32_at(template, stb_offset + 20, endian)
    column_names_offset = _u32_at(template, stb_offset + 24, endian)

    headers = tab["headers"]
    columns = tab["columns"]
    if not headers or headers[0].lower() != "id":
        raise ValueError("Risen 3 pack requires an ID column")
    hash_col = 1 if len(headers) > 1 and headers[1].lower() == "hash" else None
    text_col_start = 2 if hash_col is not None else 1
    if len(headers) - text_col_start != column_count:
        raise ValueError(
            f"Risen 3 template has {column_count} text columns, "
            f"input has {len(headers) - text_col_start}"
        )

    rows = columns_to_rows(columns)
    def row_hash(row):
        if hash_col is not None and hash_col < len(row) and row[hash_col].strip():
            return int(row[hash_col].strip().lower().removeprefix("0x"), 16) & 0xFFFFFFFF
        return parse_risen3_id(row[0], id_hash_map)

    rows.sort(key=row_hash, reverse=True)
    row_count = len(rows)
    ids = [row_hash(row) for row in rows]

    # Reuse source table and column-name block from the original binary.
    pos = source_table_offset
    for _ in range(source_count):
        length = struct.unpack_from(endian + "H", template, pos)[0]
        pos += 2 + length + 8
    source_block = template[source_table_offset:pos]

    out = bytearray()
    out += b"GAR5"
    out += flags
    out += b"STB" + bytes([version])
    out += _pack_u32(source_count, endian)
    out += _pack_u32(reserved, endian)
    out += _pack_u32(column_count, endian)
    out += _pack_u32(row_count, endian)

    source_off_pos = len(out)
    out += b"\0" * 16

    source_off = len(out)
    out += source_block

    id_table_off = len(out)
    out += _pack_u32(row_count * 4, endian)
    id_data_off = len(out) + 4
    out += _pack_u32(id_data_off, endian)
    for value in ids:
        out += _pack_u32(value, endian)

    names_off = len(out)
    name_record_size = column_count * 8
    name_data_off = names_off + name_record_size
    name_buffer = bytearray()
    for name in headers[text_col_start:]:
        encoded = str(name).encode("utf-8") + b"\0"
        out += _pack_u32(len(encoded), endian)
        out += _pack_u32(name_data_off + len(name_buffer), endian)
        name_buffer += encoded
    out += name_buffer

    column_entries = []
    for col_index in range(column_count):
        text_index = text_col_start + col_index
        texts = [row[text_index] if text_index < len(row) else "" for row in rows]
        string_table, symbol_table = _build_risen3_column(texts, endian)
        string_table_off = len(out)
        out += string_table
        symbol_table_off = len(out)
        out += symbol_table
        column_entries.append((len(string_table), string_table_off, len(symbol_table), symbol_table_off))

    column_table_off = len(out)
    for entry in column_entries:
        for value in entry:
            out += _pack_u32(value, endian)

    struct.pack_into(endian + "I", out, source_off_pos, source_off)
    struct.pack_into(endian + "I", out, source_off_pos + 4, names_off)
    struct.pack_into(endian + "I", out, source_off_pos + 8, column_table_off)
    struct.pack_into(endian + "I", out, source_off_pos + 12, id_table_off)

    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "wb") as f:
        f.write(out)


def write_tab(path, tab, target_game):
    headers = tab["headers"]
    columns = tab["columns"]
    if len(headers) != len(columns):
        raise ValueError("headers/columns length mismatch")

    game = tab.get("game", target_game)
    buf = bytearray()
    
    # Calculate a fresh filetime fallback only if missing from the imported structure
    default_filetime = int((time.time() + 11644473600) * 10_000_000)
    ts = tab.get("date_time", default_filetime)

    if game == 1:
        buf += b"TAB0"
        buf += struct.pack("<hhq", tab.get("version", 1), tab.get("format", 1), ts)
        is_unicode = True
    elif game == 2:
        buf += b"TAB1"
        is_unicode = int(tab.get("is_unicode", 1)) or 1
        buf += struct.pack("<HHQ", tab.get("version", 2), is_unicode, ts)
    else:
        raise ValueError(f"Unsupported game version: {game}")

    buf += struct.pack("<I", len(headers))
    for name, col in zip(headers, columns):
        buf += struct.pack("<BH", 1, 1)
        _wstr(buf, name, is_unicode)
        buf += struct.pack("<I", len(col))
        for s in col:
            _wstr(buf, s, is_unicode)

    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "wb") as f:
        f.write(buf)


def columns_to_rows(columns):
    if not columns:
        return []
    n = max(len(c) for c in columns)
    return [[(c[i] if i < len(c) else "") for c in columns] for i in range(n)]


def rows_to_columns(rows, ncols):
    cols = [[] for _ in range(ncols)]
    for r in rows:
        for i in range(ncols):
            cols[i].append(r[i] if i < len(r) else "")
    return cols


# ---------- file format writers / readers ----------

def dump_csv(path, tab):
    rows = columns_to_rows(tab["columns"])
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8-sig", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(tab["headers"])
        w.writerows(rows)


def load_csv(path):
    with open(path, "r", encoding="utf-8-sig", newline="") as fh:
        r = list(csv.reader(fh))
    if not r:
        raise ValueError(f"{path}: empty csv")
    headers = r[0]
    rows = r[1:]
    return {
        "headers": headers,
        "columns": rows_to_columns(rows, len(headers)),
    }


def dump_json(path, tab):
    rows = columns_to_rows(tab["columns"])
    payload = {
        "game": tab["game"],
        "version": tab["version"],
        "format": tab.get("format", 1),
        "headers": tab["headers"],
        "rows": rows,
    }
    for key in ("is_unicode", "date_time", "sources"):
        if key in tab:
            payload[key] = tab[key]
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False, indent=2)


def load_json(path):
    with open(path, "r", encoding="utf-8") as fh:
        j = json.load(fh)
    headers = j["headers"]
    if "rows" in j:
        rows = j["rows"]
        if rows and isinstance(rows[0], dict):
            rows = [[r.get(h, "") for h in headers] for r in rows]
        cols = rows_to_columns(rows, len(headers))
    elif "columns" in j:
        cols = j["columns"]
    else:
        raise ValueError(f"{path}: json must contain 'rows' or 'columns'")
    
    ret = {
        "headers": headers,
        "columns": cols,
    }
    for k in ("game", "version", "format", "is_unicode", "date_time"):
        if k in j:
            ret[k] = j[k]
    return ret


def dump_txt(path, tab):
    rows = columns_to_rows(tab["columns"])
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("\t".join(tab["headers"]) + "\n")
        for r in rows:
            fh.write("\t".join(r) + "\n")


DUMPERS = {"csv": dump_csv, "json": dump_json, "txt": dump_txt}
LOADERS = {".csv": load_csv, ".json": load_json}


# ---------- batch helpers ----------

def iter_files(root, exts):
    root = Path(root)
    if root.is_file():
        if root.suffix.lower() in exts:
            yield root, root.name
        return
    if root.is_dir():
        for p in sorted(root.rglob("*")):
            if p.is_file() and p.suffix.lower() in exts:
                yield p, str(p.relative_to(root))
        return
    raise FileNotFoundError(root)


# ---------- commands ----------

def cmd_extract(args):
    out_dir = Path(args.out) if args.out else None
    files = list(iter_files(args.input, {".tab", ".bin"}))
    if not files:
        print("No .tab or .bin string-table files found.", file=sys.stderr)
        sys.exit(1)

    id_map = None
    id_map_path = Path(args.id_map) if args.id_map else default_risen3_id_map_path()
    if id_map_path:
        try:
            id_map = load_risen3_id_map(id_map_path)
            print(f"[info] loaded Risen 3 ID map: {id_map_path} ({len(id_map)} ids)", file=sys.stderr)
        except Exception as e:
            print(f"[WARN] failed to load Risen 3 ID map {id_map_path}: {e}", file=sys.stderr)

    ok = fail = 0
    for path, rel in files:
        try:
            tab = read_string_table(path)
            mapped_count = apply_risen3_id_map(tab, id_map)
        except Exception as e:
            print(f"[FAIL] {rel}: {e}", file=sys.stderr)
            fail += 1
            continue

        if out_dir is None:
            fmt = tab.get("format", "")
            suffix = f" {fmt}" if fmt else ""
            print(f"\n=== {rel} (Risen {tab['game']}{suffix}) ===")
            print(f"v{tab['version']}  cols={len(tab['headers'])}  "
                  f"rows={len(tab['columns'][0]) if tab['columns'] else 0}")
            print("\t".join(tab["headers"]))
            for r in columns_to_rows(tab["columns"])[: args.preview]:
                print("\t".join(r))
        else:
            target = out_dir / (str(Path(rel).with_suffix("." + args.format)))
            DUMPERS[args.format](target, tab)
            print(f"[ok]   {rel} -> {target}")
        if mapped_count:
            print(f"[info] {rel}: restored {mapped_count} Risen 3 IDs", file=sys.stderr)
        ok += 1

    print(f"\nExtract summary: {ok} successful, {fail} failed", file=sys.stderr)


def cmd_pack(args):
    out_dir = Path(args.out) if args.out else None
    files = list(iter_files(args.input, set(LOADERS.keys())))
    if not files:
        print("No compatible .csv or .json files found.", file=sys.stderr)
        sys.exit(1)

    template = None
    id_hash_map = None
    if args.game == 3:
        template = Path(args.template) if args.template else Path("w_strings.bin")
        if not template.is_file():
            print(f"Risen 3 pack requires --template, not found: {template}", file=sys.stderr)
            sys.exit(1)
        id_map_path = Path(args.id_map) if args.id_map else default_risen3_id_map_path()
        if id_map_path:
            try:
                id_hash_map = load_risen3_id_hash_map(id_map_path)
                print(f"[info] loaded Risen 3 ID hash map: {id_map_path} ({len(id_hash_map)} ids)", file=sys.stderr)
            except Exception as e:
                print(f"[WARN] failed to load Risen 3 ID hash map {id_map_path}: {e}", file=sys.stderr)

    ok = fail = 0
    for path, rel in files:
        try:
            tab = LOADERS[path.suffix.lower()](path)
        except Exception as e:
            print(f"[FAIL] {rel}: {e}", file=sys.stderr)
            fail += 1
            continue

        target_suffix = ".bin" if args.game == 3 else ".tab"
        target = (out_dir if out_dir else path.parent) / (Path(rel).with_suffix(target_suffix).name
                                                          if out_dir is None
                                                          else Path(rel).with_suffix(target_suffix))
        try:
            if args.game == 3:
                write_risen3_bin(target, tab, template, id_hash_map)
            else:
                write_tab(target, tab, target_game=args.game)
        except Exception as e:
            print(f"[FAIL] {rel}: {e}", file=sys.stderr)
            fail += 1
            continue
        print(f"[ok]   {rel} -> {target} (Game {tab.get('game', args.game)})")
        ok += 1

    print(f"\nPack summary: {ok} successful, {fail} failed", file=sys.stderr)


def main():
    ap = argparse.ArgumentParser(
        description="Unified Tool for Reading and Writing Risen 1, Risen 2 (.tab), and Risen 3 (.bin) String Tables.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="Examples:\n"
               "  python risen_text.py extract localization.tab -o extracted_text/ -f csv\n"
               "  python risen_text.py extract w_strings.bin -o extracted_text/ --id-map lianzifu-unpack.risen3.csv\n"
               "  python risen_text.py pack extracted_texts/ -g 1 -o packed_out/\n"
               "  python risen_text.py pack edited_file.csv --game 3 --template w_strings.bin --id-map lianzifu-unpack.risen3.csv"
    )
    sub = ap.add_subparsers(
        dest="cmd", 
        required=True, 
        help="Available operation modes. Type '[command] -h' for specific options."
    )

    # Extract command help parser
    p_ex = sub.add_parser(
        "extract", 
        help="Convert binary string-table files (.tab / .bin) into editable text formats (CSV, JSON, or TXT).",
        description="Extracts data from string table files. Supports processing a single file or a whole directory recursively. "
                    "The script automatically detects whether a file belongs to Risen 1 (TAB0), Risen 2 (TAB1), or Risen 3 (GAR5/STB)."
    )
    p_ex.add_argument(
        "input", 
        help="Path to a single file (.tab/.bin) or a directory containing them to extract."
    )
    p_ex.add_argument(
        "-o", "--out", 
        help="Path to the output directory where extracted files will be saved. "
             "If this flag is omitted, the script will dump a raw preview directly to stdout instead of saving files."
    )
    p_ex.add_argument(
        "-f", "--format", 
        choices=("csv", "json", "txt"), 
        default="csv",
        help="The target file format to generate. 'csv' (default) preserves the grid natively with UTF-8 BOM, "
             "'json' saves complete layout structure including internal file metadata, "
             "and 'txt' outputs a plain tab-separated matrix layout."
    )
    p_ex.add_argument(
        "-n", "--preview", 
        type=int, 
        default=10,
        help="Maximum number of rows to print per file when performing a command line preview (when -o is omitted)."
    )
    p_ex.add_argument(
        "--id-map",
        help="Optional Risen 3 lianzifu-unpack.risen3.csv map. If omitted, the tool auto-loads "
             "./lianzifu-unpack.risen3.csv when present."
    )
    p_ex.set_defaults(func=cmd_extract)

    # Pack command help parser
    p_pk = sub.add_parser(
        "pack", 
        help="Compile editable text formats (CSV or JSON) back into engine binary files.",
        description="Compiles text files back into engine-compatible binary string tables. "
                    "Supports single files or batch folder conversion recursively."
    )
    p_pk.add_argument(
        "input", 
        help="Path to a single source file (.csv/.json) or a directory containing them to pack."
    )
    p_pk.add_argument(
        "-o", "--out", 
        help="Path to the destination output folder. If omitted, the generated binary files "
             "will be saved in the exact same directory alongside their corresponding source files."
    )
    p_pk.add_argument(
        "-g", "--game", 
        choices=(1, 2, 3), 
        type=int, 
        required=True,
        help="'1' for Risen 1 format (TAB0), '2' for Risen 2 format (TAB1), or '3' for Risen 3 w_strings.bin. "
             "Note: If using JSON files containing an embedded 'game' metadata key, this option will override it."
    )
    p_pk.add_argument(
        "--template",
        help="Path to the original Risen 3 w_strings.bin file to use as a structural template. "
             "This parameter is REQUIRED when packing for Risen 3 (-g 3)."
    )
    p_pk.add_argument(
        "--id-map",
        help="Optional Risen 3 lianzifu-unpack.risen3.csv map to reverse string hashes back to original text IDs. "
             "If omitted, the tool auto-loads ./lianzifu-unpack.risen3.csv when present."
    )
    p_pk.set_defaults(func=cmd_pack)

    if len(sys.argv) == 1:
        ap.print_help(sys.stderr)
        sys.exit(1)

    args = ap.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()