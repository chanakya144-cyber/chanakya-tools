import sqlite3
conn = sqlite3.connect('chanakya_tools.db')
c = conn.cursor()

print("--- പഴയ Data ---")
c.execute("SELECT id, tool_name, tool_code FROM tools")
for row in c.fetchall():
    print(row)

# എല്ലാ Empty Code-നും പുതിയ Code കൊടുക്കുന്നു
c.execute("SELECT id FROM tools WHERE tool_code IS NULL OR tool_code='' OR tool_code='None'")
rows = c.fetchall()
for r in rows:
    new_code = f"CNM-{r[0]:03d}" # ഉദാ: CNM-001, CNM-002
    c.execute("UPDATE tools SET tool_code=? WHERE id=?", (new_code, r[0]))
    print(f"Fixed ID {r[0]} -> {new_code}")

conn.commit()

print("\n--- പുതിയ Data ---")
c.execute("SELECT id, tool_name, tool_code FROM tools")
for row in c.fetchall():
    print(row)

conn.close()
print("\nDone അളിയാ! ഇനി SMS-ൽ ID ശരിയായി വരും!")