from math import floor, copysign, pi, cos, sin
from base64 import b64decode, b64encode
from re import findall, sub
from random import random
from hashlib import sha256
from struct import pack
from time import time

def generate_sign(url_path, http_method, token, svg_data, vals, timestamp=None, rand_val=None):
    ts = int(time() - 1682924400) if not timestamp else timestamp
    packed_ts = pack('<I', ts)
    decoded_token = b64decode(token)
    processed = xs(decoded_token, svg_data, vals)
    message = "!".join([http_method, url_path, str(ts)]) + "obfiowerehiring" + processed
    hash_digest = sha256(message.encode('utf-8')).digest()[:16]
    prefix = int(floor(random() if not rand_val else rand_val * 256))
    combined = bytes([prefix]) + decoded_token + packed_ts + hash_digest + bytes([3])
    byte_arr = bytearray(combined)
    if len(byte_arr) > 0:
        first_byte = byte_arr[0]
        for i in range(1, len(byte_arr)):
            byte_arr[i] = byte_arr[i] ^ first_byte
    return b64encode(bytes(byte_arr)).decode('ascii').replace('=', '')

def xs(token_bytes, svg_data, indices):
    byte_list = list(token_bytes)
    pos = byte_list[indices[0]] % 16
    multiplier = ((byte_list[indices[1]] % 16) * (byte_list[indices[2]] % 16)) * (byte_list[indices[3]] % 16)
    parsed = xa(svg_data)
    selected = parsed[pos]
    styles = simulate_style(selected, multiplier)
    combined_str = str(styles["color"]) + str(styles["transform"])
    numbers = findall(r"[\d\.\-]+", combined_str)
    hex_vals = []
    for num_str in numbers:
        float_val = float(num_str)
        hex_str = tohex(float_val)
        hex_vals.append(hex_str)
    result = "".join(hex_vals)
    cleaned = result.replace(".", "").replace("-", "")
    return cleaned

def tohex(number):
    rounded_num = round(float(number), 2)
    if rounded_num == 0.0:
        return "0"
    sign_str = "-" if copysign(1.0, rounded_num) < 0 else ""
    abs_val = abs(rounded_num)
    int_part = int(floor(abs_val))
    frac_part = abs_val - int_part
    if frac_part == 0.0:
        return sign_str + format(int_part, "x")
    hex_digits = []
    temp_frac = frac_part
    for _ in range(20):
        temp_frac *= 16
        hex_digit = int(floor(temp_frac + 1e-12))
        hex_digits.append(format(hex_digit, "x"))
        temp_frac -= hex_digit
        if abs(temp_frac) < 1e-12:
            break
    hex_frac = "".join(hex_digits).rstrip("0")
    if hex_frac == "":
        return sign_str + format(int_part, "x")
    return sign_str + format(int_part, "x") + "." + hex_frac

def simulate_style(val_array, multiplier):
    total_duration = 4096
    current_time = round(multiplier / 10.0) * 10
    time_ratio = current_time / total_duration
    control_points = [_h(val, -1 if (i % 2) else 0, 1, False) for i, val in enumerate(val_array[7:])]
    eased_progress = cubic_bezier_eased(time_ratio, control_points[0], control_points[1], control_points[2], control_points[3])
    start_rgb = [float(x) for x in val_array[0:3]]
    end_rgb = [float(x) for x in val_array[3:6]]
    red = round(start_rgb[0] + (end_rgb[0] - start_rgb[0]) * eased_progress)
    green = round(start_rgb[1] + (end_rgb[1] - start_rgb[1]) * eased_progress)
    blue = round(start_rgb[2] + (end_rgb[2] - start_rgb[2]) * eased_progress)
    rgb_color = f"rgb({red}, {green}, {blue})"
    final_angle = _h(val_array[6], 60, 360, True)
    current_angle = final_angle * eased_progress
    rad = current_angle * pi / 180.0
    cosv = cos(rad)
    sinv = sin(rad)
    if _is_effectively_zero(cosv):
        a = 0
        d = 0
    else:
        if _is_effectively_integer(cosv):
            a = int(round(cosv))
            d = int(round(cosv))
        else:
            a = f"{cosv:.6f}"
            d = f"{cosv:.6f}"
    if _is_effectively_zero(sinv):
        bval = 0
        cval = 0
    else:
        if _is_effectively_integer(sinv):
            bval = int(round(sinv))
            cval = int(round(-sinv))
        else:
            bval = f"{sinv:.7f}"
            cval = f"{(-sinv):.7f}"
    transform = f"matrix({a}, {bval}, {cval}, {d}, 0, 0)"
    return {"color": rgb_color, "transform": transform}

def xa(svg):
    s = (svg)
    substr = s[9:]
    parts = substr.split("C")
    out = []
    for part in parts:
        cleaned = sub(r"[^\d]+", " ", part).strip()
        if cleaned == "":
            nums = [0]
        else:
            nums = [int(tok) for tok in cleaned.split() if tok != ""]
        out.append(nums)
    return out

def cubic_bezier_eased(t, x1, y1, x2, y2):
    lo, hi = 0.0, 1.0
    for _ in range(80):
        mid = 0.5 * (lo + hi)
        if _bezier_helper(mid, x1, y1, x2, y2)[0] < t:
            lo = mid
        else:
            hi = mid
    u = 0.5 * (lo + hi)
    return _bezier_helper(u, x1, y1, x2, y2)[1]

def _bezier_helper(u, x1, y1, x2, y2):
    omu = 1.0 - u
    b1 = 3.0 * omu * omu * u
    b2 = 3.0 * omu * u * u
    b3 = u * u * u
    x = b1 * x1 + b2 * x2 + b3
    y = b1 * y1 + b2 * y2 + b3
    return x, y

def _h(x, _param, c, e):
    f = ((x * (c - _param)) / 255.0) + _param
    if e:
        return floor(f)
    rounded = round(float(f), 2)
    if rounded == 0.0:
        return 0.0
    return rounded

def _is_effectively_zero(val):
    return abs(val) < 1e-7

def _is_effectively_integer(val):
    return abs(val - round(val)) < 1e-7
