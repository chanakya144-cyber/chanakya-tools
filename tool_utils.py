def generate_tool_code(get_db_func, tool_name, tool_group):
    # ആദ്യത്തെ 2 ഡിജിറ്റ് CN
    prefix = "CN"
    
    # അടുത്ത 3 ഡിജിറ്റ് ടൂൾ നെയിമിൽ നിന്ന്
    name_part = ''.join(filter(str.isalpha, tool_name))[:3].upper()
    if len(name_part) < 3:
        name_part = (name_part + "XXX")[:3]
        
    # ടൂൾ ഗ്രൂപ്പിന്റെ ആദ്യ ലെറ്റർ ("and" അല്ലെങ്കിൽ "&" ന് ശേഷം വരുന്ന വാക്കിന്റെ ആദ്യ അക്ഷരം)
    # ടൂൾ ഗ്രൂപ്പിന്റെ ആദ്യ ലെറ്റർ ("and" അല്ലെങ്കിൽ "&" ന് ശേഷം വരുന്ന വാക്കിന്റെ ആദ്യ അക്ഷരം എടുക്കാൻ)
    group_part = ""
    if tool_group:
        words = tool_group.strip().split()
        for i, w in enumerate(words):
            # വരിയിൽ 'and' അല്ലെങ്കിൽ '&' കണ്ടാൽ തൊട്ടടുത്ത വാക്കിന്റെ ആദ്യ അക്ഷരം എടുക്കും
            if w.lower() in ['and', '&'] and i + 1 < len(words):
                group_part = words[i + 1][0].upper()
                break
        
        # 'and' അല്ലെങ്കിൽ '&' ഇല്ലെങ്കിൽ അല്ലെങ്കിൽ അതിനുശേഷം വേറെ വാക്ക് ഇല്ലെങ്കിൽ ആദ്യ വാക്കിന്റെ ആദ്യ അക്ഷരം എടുക്കും
        if not group_part and words:
            group_part = words[0][0].upper()
            
    if not group_part:
        group_part = "X"
        
    base_code = f"{prefix}{name_part}{group_part}"
    
    # ഡാറ്റാബേസ് കണക്ഷൻ ശരിയായ രീതിയിൽ വിളിക്കുന്നു (ഇവിടെ get_db_func() എന്ന് ബ്രാക്കറ്റ് ഇടുക)
    conn = get_db_func()
    c = conn.cursor()
    c.execute("SELECT tool_code FROM tools WHERE tool_code LIKE ? ORDER BY id DESC", (base_code + "%",))
    existing_codes = c.fetchall()
    conn.close()
    
    next_num = 1
    if existing_codes:
        numbers = []
        for code_tuple in existing_codes:
            code = code_tuple[0]
            num_str = code[len(base_code):]
            if num_str.isdigit():
                numbers.append(int(num_str))
        if numbers:
            next_num = max(numbers) + 1
            
    return f"{base_code}{str(next_num).zfill(3)}"
