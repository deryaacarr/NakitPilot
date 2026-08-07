def find_valid_vkn() -> str:
    from apps.customers.validators import _is_valid_vkn

    for i in range(1_000_000_000, 1_000_000_200):
        candidate = f"{i:010d}"
        if _is_valid_vkn(candidate):
            return candidate
    raise RuntimeError("No valid VKN found in range")


def find_valid_tckn() -> str:
    from apps.customers.validators import _is_valid_tckn

    for base in range(100_000_001, 100_000_400):
        d = [int(c) for c in f"{base:09d}"]
        odd = d[0] + d[2] + d[4] + d[6] + d[8]
        even = d[1] + d[3] + d[5] + d[7]
        d9 = ((odd * 7) - even) % 10
        d10 = (sum(d) + d9) % 10
        candidate = "".join(map(str, d)) + str(d9) + str(d10)
        if _is_valid_tckn(candidate):
            return candidate
    raise RuntimeError("No valid TCKN found")
