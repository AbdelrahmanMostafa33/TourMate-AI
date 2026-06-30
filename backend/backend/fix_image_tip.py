"""Apply Fix 3: Suppress image upload tip after user already uploaded an image."""
import re

with open('vision_chat.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Find the tip section - it has emoji chars so we need to be careful
anchor = "# ── Suggest /image if the AI asked about interests ────────"
idx = content.find(anchor)
if idx < 0:
    print("ERROR: Could not find anchor")
    exit(1)

# Read the surrounding text
section = content[idx:idx+600]
print("Found section:")
# Show printable chars only for debugging
print(repr(section[:250]))

# Now do the replacement
old = (
    '            # ── Suggest /image if the AI asked about interests \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\n'
    '            if streamed_text and not current_image_bytes and (\n'
    '                "your interests" in streamed_text.lower() or\n'
    '                any(kw in streamed_text.lower() for kw in (\n'
    '                    "upload a photo", "upload an image",\n'
    '                    "no preference", "surprise me",\n'
    '                ))\n'
    '            ):'
)

new = (
    '            # \u2500\u2500 Suggest /image if the AI asked about interests \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\n'
    '            # Only show this tip if the user hasn\'t already uploaded an image\n'
    '            if streamed_text and not current_image_bytes and not current_image_features and (\n'
    '                "your interests" in streamed_text.lower() or\n'
    '                any(kw in streamed_text.lower() for kw in (\n'
    '                    "upload a photo", "upload an image",\n'
    '                    "no preference", "surprise me",\n'
    '                ))\n'
    '            ):'
)

count = content.count(old)
print(f"Exact match count: {count}")

if count > 0:
    content = content.replace(old, new, 1)
    with open('vision_chat.py', 'w', encoding='utf-8') as f:
        f.write(content)
    print("Fix 3: Applied successfully!")
else:
    print("Fix 3: Exact match failed. Showing the target area for debugging...")
    # Show lines around the anchor
    lines = content.split('\n')
    for i, line in enumerate(lines):
        if 'Suggest /image' in line and 'interests' in line:
            for j in range(max(0, i-1), min(len(lines), i+8)):
                print(f"Line {j}: {repr(lines[j][:120])}")
            break
