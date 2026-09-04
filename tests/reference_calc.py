def shift_month(key, delta):
    year, month = map(int, key.split("-"))
    ordinal = year * 12 + month - 1 + delta
    return f"{ordinal // 12:04d}-{ordinal % 12 + 1:02d}"


def resolve(month, mode):
    return shift_month(month, -1) if mode == "known" else month


def index_amount(index_map, amount, base_month, target_month, mode):
    base = index_map[resolve(base_month, mode)]
    target = index_map[resolve(target_month, mode)]
    indexed = amount * target / base
    return indexed, indexed - amount
