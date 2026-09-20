"""Minimal dependency-free PNG reader / ICO writer.

The repository ships PNG artwork but the application asks Windows for a
``.ico``; the missing file made every ``iconbitmap`` call raise and left the app
with no icon at all.  Rather than require Pillow at build time, this module
converts the bundled PNG into a multi-resolution ICO using only the standard
library.  It supports the 8-bit RGBA PNGs used by the project.
"""

import struct
import zlib

_PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
_ICO_SIZES = (16, 24, 32, 48, 64, 256)


class ImageError(Exception):
    """Raised when the source image cannot be decoded."""


def _paeth(a, b, c):
    p = a + b - c
    pa = abs(p - a)
    pb = abs(p - b)
    pc = abs(p - c)
    if pa <= pb and pa <= pc:
        return a
    if pb <= pc:
        return b
    return c


def read_png_rgba(path):
    """Decode an 8-bit RGBA PNG into ``(width, height, bytearray)``."""
    with open(path, "rb") as stream:
        data = stream.read()

    if not data.startswith(_PNG_SIGNATURE):
        raise ImageError("not a PNG file")

    position = len(_PNG_SIGNATURE)
    header = None
    palette = None
    transparency = None
    compressed = bytearray()

    while position + 8 <= len(data):
        length, chunk_type = struct.unpack(">I4s", data[position : position + 8])
        position += 8
        payload = data[position : position + length]
        position += length + 4  # skip CRC

        if chunk_type == b"IHDR":
            header = struct.unpack(">IIBBBBB", payload)
        elif chunk_type == b"PLTE":
            palette = payload
        elif chunk_type == b"tRNS":
            transparency = payload
        elif chunk_type == b"IDAT":
            compressed.extend(payload)
        elif chunk_type == b"IEND":
            break

    if header is None:
        raise ImageError("missing IHDR chunk")

    width, height, depth, color_type, compression, filtering, interlace = header
    if depth != 8:
        raise ImageError(f"unsupported bit depth: {depth}")
    if compression != 0 or filtering != 0:
        raise ImageError("unsupported PNG compression/filter method")
    if interlace != 0:
        raise ImageError("interlaced PNGs are not supported")

    channels_by_color_type = {0: 1, 2: 3, 3: 1, 4: 2, 6: 4}
    if color_type not in channels_by_color_type:
        raise ImageError(f"unsupported colour type: {color_type}")
    channels = channels_by_color_type[color_type]

    if color_type == 3 and not palette:
        raise ImageError("indexed PNG without palette")

    raw = zlib.decompress(bytes(compressed))
    stride = width * channels
    expected = (stride + 1) * height
    if len(raw) < expected:
        raise ImageError("truncated image data")

    pixels = bytearray(stride * height)
    previous = bytearray(stride)
    offset = 0

    for row in range(height):
        filter_type = raw[offset]
        offset += 1
        line = bytearray(raw[offset : offset + stride])
        offset += stride

        if filter_type == 1:
            for index in range(channels, stride):
                line[index] = (line[index] + line[index - channels]) & 0xFF
        elif filter_type == 2:
            for index in range(stride):
                line[index] = (line[index] + previous[index]) & 0xFF
        elif filter_type == 3:
            for index in range(stride):
                left = line[index - channels] if index >= channels else 0
                line[index] = (line[index] + ((left + previous[index]) >> 1)) & 0xFF
        elif filter_type == 4:
            for index in range(stride):
                left = line[index - channels] if index >= channels else 0
                up_left = previous[index - channels] if index >= channels else 0
                line[index] = (
                    line[index] + _paeth(left, previous[index], up_left)
                ) & 0xFF
        elif filter_type != 0:
            raise ImageError(f"unknown filter type: {filter_type}")

        pixels[row * stride : (row + 1) * stride] = line
        previous = line

    return width, height, _to_rgba(pixels, width, height, channels, color_type, palette, transparency)


def _to_rgba(pixels, width, height, channels, color_type, palette, transparency):
    """Normalise decoded scanlines to tightly packed RGBA."""
    if color_type == 6:
        return pixels

    rgba = bytearray(width * height * 4)
    count = width * height

    for index in range(count):
        source = index * channels
        target = index * 4
        if color_type == 0:
            grey = pixels[source]
            rgba[target : target + 4] = bytes((grey, grey, grey, 255))
        elif color_type == 4:
            grey = pixels[source]
            rgba[target : target + 4] = bytes((grey, grey, grey, pixels[source + 1]))
        elif color_type == 2:
            rgba[target : target + 3] = pixels[source : source + 3]
            rgba[target + 3] = 255
        else:  # indexed
            entry = pixels[source] * 3
            if entry + 3 > len(palette):
                raise ImageError("palette index out of range")
            alpha = 255
            if transparency and pixels[source] < len(transparency):
                alpha = transparency[pixels[source]]
            rgba[target : target + 3] = palette[entry : entry + 3]
            rgba[target + 3] = alpha

    return rgba


def resize_rgba(pixels, width, height, new_width, new_height):
    """Box-filter (area average) resample, which downscales artwork cleanly."""
    if (width, height) == (new_width, new_height):
        return bytearray(pixels)

    output = bytearray(new_width * new_height * 4)
    x_ratio = width / new_width
    y_ratio = height / new_height

    for target_y in range(new_height):
        start_y = int(target_y * y_ratio)
        end_y = max(start_y + 1, int((target_y + 1) * y_ratio))
        end_y = min(end_y, height)

        for target_x in range(new_width):
            start_x = int(target_x * x_ratio)
            end_x = max(start_x + 1, int((target_x + 1) * x_ratio))
            end_x = min(end_x, width)

            alpha_sum = 0
            red_sum = 0
            green_sum = 0
            blue_sum = 0
            samples = 0

            for source_y in range(start_y, end_y):
                row_offset = source_y * width * 4
                for source_x in range(start_x, end_x):
                    offset = row_offset + source_x * 4
                    alpha = pixels[offset + 3]
                    # Weight colour by alpha so transparent pixels do not darken edges.
                    alpha_sum += alpha
                    red_sum += pixels[offset] * alpha
                    green_sum += pixels[offset + 1] * alpha
                    blue_sum += pixels[offset + 2] * alpha
                    samples += 1

            target = (target_y * new_width + target_x) * 4
            if alpha_sum:
                output[target] = min(255, round(red_sum / alpha_sum))
                output[target + 1] = min(255, round(green_sum / alpha_sum))
                output[target + 2] = min(255, round(blue_sum / alpha_sum))
            output[target + 3] = round(alpha_sum / samples) if samples else 0

    return output


def _ico_image_entry(pixels, width, height):
    """Build one ICO directory entry (BITMAPINFOHEADER + BGRA + AND mask)."""
    header = struct.pack(
        "<IiiHHIIiiII",
        40,          # biSize
        width,
        height * 2,  # XOR + AND mask
        1,           # biPlanes
        32,          # biBitCount
        0,           # biCompression (BI_RGB)
        width * height * 4,
        0,
        0,
        0,
        0,
    )

    xor_mask = bytearray(width * height * 4)
    for y in range(height):
        source_row = (height - 1 - y) * width * 4  # ICO rows are bottom-up
        target_row = y * width * 4
        for x in range(width):
            source = source_row + x * 4
            target = target_row + x * 4
            xor_mask[target] = pixels[source + 2]      # blue
            xor_mask[target + 1] = pixels[source + 1]  # green
            xor_mask[target + 2] = pixels[source]      # red
            xor_mask[target + 3] = pixels[source + 3]  # alpha

    mask_stride = ((width + 31) // 32) * 4
    and_mask = bytes(mask_stride * height)

    return header + bytes(xor_mask) + and_mask


def png_to_ico(source_path, target_path, sizes=_ICO_SIZES):
    """Convert an RGBA PNG into a multi-size ICO file."""
    width, height, pixels = read_png_rgba(source_path)

    entries = []
    for size in sizes:
        if size > max(width, height):
            continue
        resized = resize_rgba(pixels, width, height, size, size)
        entries.append((size, _ico_image_entry(resized, size, size)))

    if not entries:
        raise ImageError("no icon size fits the source image")

    directory = bytearray()
    offset = 6 + 16 * len(entries)
    images = bytearray()

    for size, image in entries:
        directory.extend(
            struct.pack(
                "<BBBBHHII",
                0 if size >= 256 else size,
                0 if size >= 256 else size,
                0,   # palette colours
                0,   # reserved
                1,   # colour planes
                32,  # bits per pixel
                len(image),
                offset,
            )
        )
        images.extend(image)
        offset += len(image)

    header = struct.pack("<HHH", 0, 1, len(entries))  # reserved, type=icon, count

    with open(target_path, "wb") as stream:
        stream.write(header + bytes(directory) + bytes(images))

    return target_path, [size for size, _ in entries]


def write_placeholder_ico(target_path, size=64, color=(33, 150, 243, 255)):
    """Write a solid square icon - last-resort fallback if artwork is missing."""
    pixels = bytearray()
    for _ in range(size * size):
        pixels.extend(color)
    image = _ico_image_entry(pixels, size, size)
    header = struct.pack("<HHH", 0, 1, 1)
    directory = struct.pack("<BBBBHHII", size, size, 0, 0, 1, 32, len(image), 22)
    with open(target_path, "wb") as stream:
        stream.write(header + directory + image)
    return target_path


if __name__ == "__main__":  # manual regeneration helper
    import sys

    source = sys.argv[1] if len(sys.argv) > 1 else "volume_icon.png"
    target = sys.argv[2] if len(sys.argv) > 2 else "volume_icon.ico"
    print(png_to_ico(source, target))
