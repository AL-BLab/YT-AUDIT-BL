import os
import sys
import subprocess
import json
import re

def run_step(command, step_name):
    print(f"\n🚀 Running Step: {step_name}...")
    try:
        # Use shell=True to handle spaces and paths properly in this context
        # But for security/stability, we could use list format if needed.
        # Given the requirements, we'll use a robust approach.
        process = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        
        # We need to capture the output to find the channel_id in step 1
        full_output = ""
        for line in process.stdout:
            print(line, end="")
            full_output += line
        
        process.wait()
        
        if process.returncode != 0:
            print(f"❌ Error in {step_name}")
            return False, full_output
        
        return True, full_output
    except Exception as e:
        print(f"❌ Exception in {step_name}: {e}")
        return False, str(e)

def main():
    if len(sys.argv) < 2:
        print("Usage: python3 main.py \"CHANNEL_URL\"")
        sys.exit(1)

    channel_url = sys.argv[1]
    
    # Ensure reports directory exists
    os.makedirs("reports", exist_ok=True)

    # Step 1: Fetch Data
    success, output = run_step(f"python3 tools/youtube_fetch_channel_data.py \"{channel_url}\"", "Fetching Channel Data")
    if not success:
        sys.exit(1)

    # Extract channel_id from output
    # Looking for: "Channel ID: (UC...)" or similar
    match = re.search(r"Channel ID: ([A-Za-z0-9_-]+)", output)
    if not match:
        print("❌ Could not determine Channel ID from output.")
        sys.exit(1)

    channel_id = match.group(1).strip()
    print(f"✅ Identified Channel ID: {channel_id}")

    raw_data_path = f".tmp/youtube_audits/{channel_id}/raw_data.json"
    analysis_path = f".tmp/youtube_audits/{channel_id}/analysis.json"

    # Step 2: Analyze
    success, _ = run_step(f"python3 tools/youtube_analyze_videos.py {raw_data_path}", "Analyzing Videos")
    if not success:
        sys.exit(1)

    # Step 3: Export to Excel
    success, _ = run_step(f"python3 tools/export_to_excel.py {raw_data_path} {analysis_path}", "Exporting to Excel")
    if not success:
        # We don't exit here because we still want to generate the markdown report
        print("⚠️ Excel export failed, proceeding to Markdown report.")

    # Step 4: Generate Markdown Report
    success, _ = run_step(f"python3 tools/generate_markdown_report.py {raw_data_path} {analysis_path}", "Generating Markdown Report")
    
    # Step 5: Copy report to reports directory
    source_report = f".tmp/youtube_audits/{channel_id}/report.md"
    target_report = f"reports/{channel_id}_report.md"
    
    if os.path.exists(source_report):
        try:
            import shutil
            shutil.copy(source_report, target_report)
            print(f"\n✨ Final report copied to: {target_report}")
        except Exception as e:
            print(f"⚠️ Could not copy report to reports/ archive: {e}")

    # Step 6: Copy Excel to reports directory
    source_excel = f".tmp/youtube_audits/{channel_id}/audit_report.xlsx"
    target_excel = f"reports/{channel_id}_audit.xlsx"

    if os.path.exists(source_excel):
        try:
            import shutil
            shutil.copy(source_excel, target_excel)
            print(f"✨ Final Excel audit copied to: {target_excel}")
        except Exception as e:
            print(f"⚠️ Could not copy Excel audit to reports/ archive: {e}")

    print("\n✅ Audit Pipeline Complete!")

if __name__ == "__main__":
    main()
