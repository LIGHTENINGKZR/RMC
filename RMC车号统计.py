import os
import re
import shutil

def parse_entry_tokens(tokens):
    """
    解析一侧（或一行）的“可选姓名 + 车号 + 可选闲置数”。
    返回 (number, unused, name) 或 None（无法解析）。
    规则：
      - 若 tokens[0] 是数字：
          形如 [num, unused?] -> name=""
      - 若 tokens[0] 非数字：
          形如 [name, num, unused?]
      - unused 缺省为 0
    """
    if not tokens:
        return None
    # 情况A：首项是数字
    if tokens[0].isdigit():
        if len(tokens) >= 2 and tokens[1].isdigit():
            return (int(tokens[0]), int(tokens[1]), "")
        elif len(tokens) == 1:
            return (int(tokens[0]), 0, "")
        else:
            return None
    # 情况B：首项是姓名（非数字）
    name = tokens[0]
    if len(tokens) >= 2 and tokens[1].isdigit():
        if len(tokens) >= 3 and tokens[2].isdigit():
            return (int(tokens[1]), int(tokens[2]), name)
        else:
            return (int(tokens[1]), 0, name)
    return None

def read_tables_from_txt(file_path):
    """
    支持两种输入格式（顺序/并排）。
    并排模式修复：若某行第一个字符是空白(空格/Tab)，视为“左列已结束，该行只属于右列(C2)”。
    现在每条记录支持“姓名 车号 闲置数”，姓名可缺省。
    内部统一存储为 (number, unused, name)
    """
    tables = {"C1": [], "C2": []}

    with open(file_path, "r", encoding="utf-8") as f:
        lines = [ln.rstrip("\n") for ln in f]

    # 判定是否为并排格式：存在一行同时含 "C1" 和 "C2" 的标题
    side_by_side = any(("C1" in ln and "C2" in ln) for ln in lines if ln.strip())

    if side_by_side:
        for raw_line in lines:
            if not raw_line.strip():
                continue

            stripped = raw_line.strip()

            # 跳过表头/标题行
            if "车号" in stripped:
                continue
            if ("C1" in stripped and "C2" in stripped and not any(ch.isdigit() for ch in stripped)):
                continue

            # 若该行首字符是空白 => 只解析为右列(C2)
            if raw_line[:1].isspace():
                toks = stripped.split()
                rec = parse_entry_tokens(toks)
                if rec:
                    tables["C2"].append(rec)
                continue

            # 并排行：用“≥2个Tab 或 ≥3个空格”切成左右两块
            parts = re.split(r'(?:\t{2,}|\s{3,})', raw_line)
            if len(parts) >= 2:
                left = parts[0].strip()
                right = parts[1].strip()

                lt = left.split()
                rec_l = parse_entry_tokens(lt)
                if rec_l:
                    tables["C1"].append(rec_l)

                rt = right.split()
                rec_r = parse_entry_tokens(rt)
                if rec_r:
                    tables["C2"].append(rec_r)
            else:
                # 无明显分隔符 => 仅左列 C1
                lt = stripped.split()
                rec_l = parse_entry_tokens(lt)
                if rec_l:
                    tables["C1"].append(rec_l)

    else:
        # 顺序（分块）模式
        current_key = None
        for ln in lines:
            line = ln.strip()
            if not line:
                continue

            if line in ("C1", "C2"):
                current_key = line
                continue

            if line.startswith("车号"):
                continue

            if current_key is not None:
                tokens = line.split()
                rec = parse_entry_tokens(tokens)
                if rec:
                    tables[current_key].append(rec)

    # 最后按车号排序，保持稳定
    tables["C1"] = sorted(tables.get("C1", []), key=lambda x: x[0])
    tables["C2"] = sorted(tables.get("C2", []), key=lambda x: x[0])
    return tables


def collect_numbers_from_input(table_name):
    """
    整体更新：仍只收车号（不输入姓名）。
    """
    print(f"请输入本赛季 {table_name} 已使用的车号（输入 # 结束）：")
    nums = []
    while True:
        try:
            line = input()
        except EOFError:
            break
        if line is None:
            break
        line = line.strip()
        if line.upper() == "#":
            break
        if line == "":
            continue
        for tok in line.split():
            if tok.isdigit():
                nums.append(int(tok))
            else:
                print(f"  ⚠️ 跳过非数字项：{tok}")
    return nums

def update_table_rows(rows, new_numbers, max_unused=3, increment_absent=True):
    """
    rows: [(number, unused, name), ...]
    new_numbers: [n1, n2, ...]
    规则（通用）：
      - 若 number 在本次输入中出现 -> unused = 0（存在则清零；不存在则新增为0, name=""）
      - 若 number 未在本次输入中出现:
          * increment_absent=True  -> unused += 1；若 unused >= max_unused，则删除该条
          * increment_absent=False -> unused 保持不变（不删除）
      - 最后按 number 升序排序
    """
    # 构造 num -> (unused, name)
    d = {num: (unused, name) for (num, unused, name) in rows}
    new_set = set(new_numbers)

    if increment_absent:
        # 未出现的旧号码：unused+1，达到阈值删除
        to_delete = []
        for num in list(d.keys()):
            if num not in new_set:
                old_unused, old_name = d[num]
                new_unused = old_unused + 1
                if new_unused >= max_unused:
                    to_delete.append(num)
                else:
                    d[num] = (new_unused, old_name)
        for num in to_delete:
            del d[num]
    else:
        # 不递增未出现者：完全保持旧 unused 与存在性
        # （什么都不做）
        pass

    # 本次出现的号码：置 unused=0；新号则 name=""
    for n in new_set:
        old = d.get(n)
        if old is not None:
            _, old_name = old
            d[n] = (0, old_name)
        else:
            d[n] = (0, "")

    # 还原为列表并排序
    out = [(num, unused, name) for num, (unused, name) in d.items()]
    return sorted(out, key=lambda x: x[0])


def write_tables_to_txt(output_path, tables):
    """
    输出为双并排格式：
    C1                      C2
    车手 车号 闲置赛季数        车手 车号 闲置赛季数
    张三 5 0                 李四 0 0
    ...
    """
    rows1 = sorted(tables.get("C1", []), key=lambda x: x[0])  # (num, unused, name)
    rows2 = sorted(tables.get("C2", []), key=lambda x: x[0])
    max_len = max(len(rows1), len(rows2))

    with open(output_path, "w", encoding="utf-8", newline="\n") as f:
        # 表头
        f.write("C1\t\t\tC2\n")
        f.write("车手 车号 闲置赛季数\t\t车手 车号 闲置赛季数\n")

        # 每一行写 C1 和 C2（姓名在最左）
        for i in range(max_len):
            if i < len(rows1):
                n1, u1, name1 = rows1[i]
                left = f"{name1} {n1} {u1}".strip()
            else:
                left = ""
            if i < len(rows2):
                n2, u2, name2 = rows2[i]
                right = f"{name2} {n2} {u2}".strip()
            else:
                right = ""
            f.write(f"{left}\t\t{right}\n")

        f.write("\n车号选择范围：0，2-999未选号码\n")

        # 车号列表汇总（空表时输出空字符串）
        for key, rows in (("C1", rows1), ("C2", rows2)):
            numbers_str = ",".join(str(num) for num, _, _ in rows)
            f.write(f"{key} 已使用车号: {numbers_str}\n")
        
        f.write("车号具体使用人见《 车号统计》\n")

    return output_path

#==================== 单个增加/修改 ====================#
def set_single_entry(tables, table_key, car_no, new_unused, name="", max_unused=3):
    """
    单个车号的增加/修改：
      - 若不存在：新增 (car_no, new_unused, name)
      - 若存在：覆盖 unused，若 name 非空则更新 name（否则保留原 name）
      - 若 new_unused >= max_unused：直接删除该车号
      - 最后按车号升序
    """
    if table_key not in tables:
        tables[table_key] = []

    # num -> (unused, name)
    d = {num: (unused, nm) for num, unused, nm in tables[table_key]}
    if new_unused >= max_unused:
        if car_no in d:
            del d[car_no]
    else:
        old = d.get(car_no)
        if old is None:
            d[car_no] = (new_unused, name or "")
        else:
            _, old_name = old
            d[car_no] = (new_unused, name if name else old_name)

    tables[table_key] = sorted([(num, unused, nm) for num, (unused, nm) in d.items()],
                               key=lambda x: x[0])

def ask_single_edit():
    """
    允许输入以下任一种：
      - 姓名 车号 闲置数
      - 姓名 车号
      - 车号 闲置数
      - 车号
    """
    while True:
        key = input("请选择表（1 或 2）：").strip()
        if key in ("1", "2"):
            key = "C" + key
            break
        print("无效表名，请输入 1 或 2。")

    while True:
        entry = input("请输入（可选姓名）车号（可选闲置数），例如：“张三 15 2”/“张三 15”/“15 2”/“15”：").strip()
        if not entry:
            print("输入不能为空。")
            continue
        parts = entry.split()

        # 情况A：首项是数字 -> 无姓名
        if parts[0].isdigit():
            if len(parts) >= 2 and parts[1].isdigit():
                car_no = int(parts[0]); new_unused = int(parts[1]); name = ""
                break
            elif len(parts) == 1:
                car_no = int(parts[0]); new_unused = 0; name = ""
                break
        else:
            # 情况B：首项是姓名
            name = parts[0]
            if len(parts) >= 2 and parts[1].isdigit():
                car_no = int(parts[1])
                if len(parts) >= 3 and parts[2].isdigit():
                    new_unused = int(parts[2])
                else:
                    new_unused = 0
                break

        print("输入格式错误，请重试。")
    return key, car_no, new_unused, name

#==================== 删除号码 ====================#
def choose_mode():
    print("请选择操作模式：")
    print("1. 新赛季车号统计更新")
    print("2. 季中转会车号统计更新") 
    print("3. 单个车号信息 增加/修改（支持姓名）")
    print("4. 车号删除")
    print("5. 只运行写出并退出")
    while True:
        choice = input("请输入 1 / 2 / 3 / 4 / 5：").strip()
        if choice in ("1", "2", "3", "4", "5"):
            return choice
        print("无效输入，请重新输入。")

def delete_entry(tables):
    while True:
        key = input("请选择要删除的表（1 或 2）：").strip()
        if key in ("1", "2"):
            key = "C" + key
            break
        print("无效输入，请输入 1 或 2。")

    raw = input("请输入要删除的车号（可多个，空格或逗号分隔，例如：15 23,68）：").strip()
    tokens = [t for t in re.split(r"[,\s]+", raw) if t]
    nums = []
    for t in tokens:
        if t.isdigit():
            nums.append(int(t))
        else:
            print(f"  ⚠️ 跳过非数字项：{t}")
    if not nums:
        print("⚠️ 未输入有效车号，取消删除。")
        return

    before = len(tables.get(key, []))
    to_remove = set(nums)
    tables[key] = [(n, u, nm) for (n, u, nm) in tables.get(key, []) if n not in to_remove]
    tables[key] = sorted(tables[key], key=lambda x: x[0])

    removed = before - len(tables[key])
    if removed > 0:
        print(f"✅ 已从 {key} 删除 {removed} 条记录（车号：{', '.join(map(str, nums))}）。")
    else:
        print(f"⚠️ {key} 中未找到指定车号：{', '.join(map(str, nums))}")

#==================== 主程序 ====================#
if __name__ == "__main__":
    file_path = "C:/Users/用户名/Desktop/RMC/车号统计/车号记录.txt"   # 原始数据文件
    tables = read_tables_from_txt(file_path)
    tables.setdefault("C1", [])
    tables.setdefault("C2", [])

    mode = choose_mode()
    MAX_UNUSED = 3  # 达到该阈值即删除（整体更新时）

    if mode == "1":
        # 整体更新（仍只输入车号）
        input_c1 = collect_numbers_from_input("C1")
        input_c2 = collect_numbers_from_input("C2")
        tables["C1"] = update_table_rows(tables["C1"], input_c1, max_unused=MAX_UNUSED)
        tables["C2"] = update_table_rows(tables["C2"], input_c2, max_unused=MAX_UNUSED)
    
    elif mode == "2":
        # 整体更新，但不递增未出现号码的闲置数
        input_c1 = collect_numbers_from_input("C1")
        input_c2 = collect_numbers_from_input("C2")
        tables["C1"] = update_table_rows(
            tables["C1"], input_c1, max_unused=MAX_UNUSED, increment_absent=False
        )
        tables["C2"] = update_table_rows(
            tables["C2"], input_c2, max_unused=MAX_UNUSED, increment_absent=False
        )

    elif mode == "3":
        # 单个增改（可带姓名）
        key, car_no, new_unused, name = ask_single_edit()
        set_single_entry(tables, key, car_no, new_unused, name=name, max_unused=MAX_UNUSED)

    elif mode == "4":
        # 删除号码
        delete_entry(tables)

    elif mode == "5":
        # 只写出并退出
        base, ext = os.path.splitext(file_path)
        backup_path = base + "_backup" + ext
        shutil.copy2(file_path, backup_path)
        write_tables_to_txt(file_path, tables)
        print(f"✅ 已写入：{file_path}\n📂 备份文件：{backup_path}")
        raise SystemExit(0)


    # === 写回原文件（覆盖写入前先备份） ===
    base, ext = os.path.splitext(file_path)
    backup_path = base + "_backup" + ext
    shutil.copy2(file_path, backup_path)   # 创建备份
    write_tables_to_txt(file_path, tables) # 覆盖写原文件

    print(f"✅ 已写入：{file_path}\n📂 备份文件：{backup_path}")
