import os
from pathlib import Path
import shutil
import tempfile

import zstandard


MAX_SEED_SIZE = 50 * 1024 * 1024
SEED_FILES = ('VariationsSeedV2', 'VariationsSafeSeedV2')


def read_varint(data, offset):
    value = 0
    for shift in range(0, 70, 7):
        if offset >= len(data):
            raise ValueError('Truncated protobuf varint')
        byte = data[offset]
        offset += 1
        if shift == 63 and byte > 1:
            raise ValueError('Protobuf varint exceeds 64 bits')
        value |= (byte & 0x7f) << shift
        if not byte & 0x80:
            return value, offset
    raise ValueError('Invalid protobuf varint')


def patch_seed_countries(data):
    # StoredSeedInfo fields 6 and 7 hold session and permanent country codes:
    # https://chromium.googlesource.com/chromium/src/+/refs/tags/155.0.8059.80/components/variations/proto/stored_seed_info.proto
    # Preserve every other field verbatim, including signed seed data and
    # unknown fields, rather than decoding and reserializing the whole message.
    chunks = []
    seen = set()
    offset = 0
    while offset < len(data):
        start = offset
        key, offset = read_varint(data, offset)
        field, wire = key >> 3, key & 7
        if not 0 < field < 1 << 29:
            raise ValueError('Invalid protobuf field number')
        if wire == 2:
            size, offset = read_varint(data, offset)
            offset += size
        elif wire == 0:
            _, offset = read_varint(data, offset)
        elif wire == 1:
            offset += 8
        elif wire == 5:
            offset += 4
        else:
            raise ValueError('Unsupported protobuf wire type')
        if offset > len(data):
            raise ValueError('Truncated protobuf field')
        if field in (6, 7):
            if wire != 2:
                raise ValueError('Country field is not length-delimited')
            chunks.append(bytes((field << 3 | 2, 2)) + b'us')
            seen.add(field)
        else:
            chunks.append(data[start:offset])
    for field in (6, 7):
        if field not in seen:
            chunks.append(bytes((field << 3 | 2, 2)) + b'us')
    return b''.join(chunks)


def patch_variations_seeds(user_data_path):
    pending = []
    # Validate both files before writing either one or changing Local State.
    for name in SEED_FILES:
        path = Path(user_data_path) / name
        if not path.exists():
            continue
        original = path.read_bytes()
        try:
            size = zstandard.frame_content_size(original)
            if size < 0 or size > MAX_SEED_SIZE:
                raise ValueError('Invalid or oversized Zstandard seed frame')
            data = zstandard.ZstdDecompressor().decompress(
                original, max_output_size=MAX_SEED_SIZE, allow_extra_data=False)
            patched = patch_seed_countries(data)
        except (ValueError, zstandard.ZstdError) as error:
            raise ValueError('Cannot patch %s: %s' % (path, error)) from error
        if patched != data:
            compressed = zstandard.ZstdCompressor(level=2).compress(patched)
            pending.append((path, original, compressed))

    for path, original, compressed in pending:
        backup = Path(str(path) + '.bak')
        try:
            with backup.open('xb') as fp:
                fp.write(original)
        except FileExistsError:
            pass  # Keep the first backup across repeated runs.
        descriptor, temporary_path = tempfile.mkstemp(
            prefix='.' + path.name + '-', dir=path.parent)
        try:
            with os.fdopen(descriptor, 'wb') as fp:
                fp.write(compressed)
                fp.flush()
                os.fsync(fp.fileno())
            shutil.copymode(path, temporary_path)
            os.replace(temporary_path, path)
        finally:
            if os.path.exists(temporary_path):
                os.unlink(temporary_path)
        print('Patched country fields in', path.name, '(backup:', str(backup) + ')')
