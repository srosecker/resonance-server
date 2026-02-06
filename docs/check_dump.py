import os


def check_file(filename):
    print(f"Analyzing {filename}...")

    if not os.path.exists(filename):
        print(f"Error: File {filename} not found.")
        return

    try:
        with open(filename, 'rb') as f:
            content = f.read()

        print(f"File size: {len(content)} bytes")

        # 1. Check for SqueezeNetwork DNS queries (evidence of State Gate / Setup Wizard)
        # DNS wire format usually has length prefixes, but the ASCII strings remain intact.
        sn_terms = [
            b"squeezenetwork",
            b"mysqueezebox",
            b"baby.squeezenetwork.com",
            b"fab4.squeezenetwork.com",
            b"jive.squeezenetwork.com",
        ]

        found_sn = False
        print("\n--- DNS / SqueezeNetwork Check ---")
        for term in sn_terms:
            count = content.count(term)
            if count > 0:
                print(f"[!] Found '{term.decode('utf-8', errors='ignore')}' {count} times")
                found_sn = True

        if not found_sn:
            print("[-] No obvious text-based SqueezeNetwork patterns found.")
        else:
            print(">>> CONCLUSION: Device is likely trying to contact Logitech servers (Setup/SN State).")

        # 2. Check for HTTP / Cometd (evidence of working connection)
        http_terms = [
            b"POST /cometd",
            b"GET /",
            b"SupportedConnectionTypes", # JSON body often has this
            b"application/json",
        ]

        found_http = False
        print("\n--- HTTP / Cometd Check ---")
        for term in http_terms:
            count = content.count(term)
            if count > 0:
                print(f"[+] Found '{term.decode('utf-8', errors='ignore')}' {count} times")
                found_http = True

        if not found_http:
            print("[-] No HTTP traffic detected (No 'POST /cometd').")
            print(">>> CONCLUSION: The device is NOT attempting to connect via HTTP.")
        else:
            print(">>> CONCLUSION: HTTP traffic is present.")

        # 3. Check for Discovery Response artifacts (Resonance side)
        # We look for the JSON port definition in the TLV
        # JSON = 'JSON' (0x4a534f4e) + len (0x04) + '9000' (0x39303030)

        # 'JSON' + len 4 + '9000'
        tlv_json_9000 = b'JSON\x049000'
        # 'VERS' + len 5 + '7.9.1'
        tlv_vers_791 = b'VERS\x057.9.1'

        print("\n--- Discovery TLV Check (Resonance Responses) ---")
        if tlv_json_9000 in content:
            print("[+] Found correct JSON TLV: JSON='9000'")
        else:
            print("[-] JSON='9000' TLV not found (might be different port or not captured).")

        if tlv_vers_791 in content:
            print("[+] Found correct VERS TLV: VERS='7.9.1'")
        else:
            print("[-] VERS='7.9.1' TLV not found.")

    except Exception as e:
        print(f"An error occurred: {e}")

if __name__ == "__main__":
    # Look for the file in the current directory or common paths
    target_files = [
        "ws21.pcapng",
        os.path.join("docs", "ws21.pcapng"),
        os.path.join("resonance-server", "docs", "ws21.pcapng")
    ]

    found = False
    for f in target_files:
        if os.path.exists(f):
            check_file(f)
            found = True
            break

    if not found:
        print("Could not find ws21.pcapng in current directory or docs/ folder.")
        print(f"Current working directory: {os.getcwd()}")
