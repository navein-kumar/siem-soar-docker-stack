#!/usr/bin/env python3
"""
Wazuh Report Engine
Takes screenshots of OpenSearch Dashboard pages and generates branded PDF reports.
Config-driven: one YAML file per client, no coding needed.
"""

import argparse
import base64
import os
import smtplib
import sys
from datetime import datetime, timedelta, timezone
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

import requests
import yaml
from jinja2 import Environment, FileSystemLoader
from playwright.sync_api import sync_playwright


# IST timezone
IST = timezone(timedelta(hours=5, minutes=30))


def load_config(config_path: str) -> dict:
    """Load client YAML config."""
    with open(config_path) as f:
        return yaml.safe_load(f)


def take_screenshots(config: dict) -> list[dict]:
    """Login to OpenSearch Dashboard and screenshot each section."""
    dash = config["opensearch_dashboard"]
    base_url = dash["url"].rstrip("/")
    sections = config.get("sections", [])
    screenshots = []

    print(f"[*] Launching browser for {base_url}")

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-gpu", "--disable-dev-shm-usage"],
        )
        context = browser.new_context(
            ignore_https_errors=True,
            viewport={"width": 1920, "height": 1080},
        )
        page = context.new_page()

        # Login to OpenSearch Dashboard
        print("[*] Logging in to OpenSearch Dashboard...")
        page.goto(f"{base_url}/app/login", wait_until="networkidle", timeout=30000)
        page.wait_for_timeout(2000)

        # Fill login form
        try:
            page.fill('input[data-test-subj="user-name"]', dash["username"], timeout=5000)
            page.fill('input[data-test-subj="password"]', dash["password"], timeout=5000)
            page.click('button[data-test-subj="log-in"]', timeout=5000)
        except Exception:
            # Fallback: try generic input selectors
            try:
                page.fill('input[name="username"]', dash["username"], timeout=5000)
                page.fill('input[name="password"]', dash["password"], timeout=5000)
                page.click('button[type="submit"]', timeout=5000)
            except Exception:
                # Try placeholder-based selectors
                page.fill('input[placeholder*="ser"]', dash["username"], timeout=5000)
                page.fill('input[placeholder*="ass"]', dash["password"], timeout=5000)
                page.press('input[placeholder*="ass"]', "Enter")

        page.wait_for_timeout(3000)
        print("[+] Login successful")

        # Dismiss any popups/modals
        try:
            page.click('button[data-test-subj="closeTourBtn"]', timeout=2000)
        except Exception:
            pass
        try:
            page.click(".euiModal button.euiButton--primary", timeout=2000)
        except Exception:
            pass

        # Screenshot each section
        for i, section in enumerate(sections):
            name = section["name"]
            url = section["url"]
            wait_for = section.get("wait_for", ".euiFlexGroup")
            wait_time = section.get("wait_time", 5)

            full_url = f"{base_url}{url}"
            print(f"[*] Capturing: {name} ({i+1}/{len(sections)})")

            page.goto(full_url, wait_until="networkidle", timeout=60000)

            # Wait for content to render
            try:
                page.wait_for_selector(wait_for, timeout=15000)
            except Exception:
                print(f"  [!] Selector '{wait_for}' not found, continuing anyway")

            # Extra wait for visualizations to load
            page.wait_for_timeout(wait_time * 1000)

            # Hide sidebar/header/chrome for cleaner screenshot
            page.evaluate("""
                // Hide top header bar (Wazuh logo, API selector, user icon)
                document.querySelectorAll('.euiHeader, .euiHeaderSection, .headerGlobalNav, .euiNavDrawer, .euiCollapsibleNav').forEach(e => e.style.display = 'none');
                document.querySelectorAll('.euiBreadcrumbs, .euiHeaderBreadcrumbs').forEach(e => e.style.display = 'none');
                // Remove top padding/margin left by hidden header
                const main = document.querySelector('.application, .app-container, main, .euiPageBody');
                if (main) { main.style.marginLeft = '0'; main.style.paddingTop = '0'; }
                // Adjust body to remove header space
                const headerBanner = document.querySelector('.euiHeaderSpacer, #globalHeaderBars');
                if (headerBanner) headerBanner.style.display = 'none';
                document.body.style.paddingTop = '0';
                // Remove any top offset on the app wrapper
                const appWrapper = document.querySelector('.app-wrapper, .application');
                if (appWrapper) { appWrapper.style.paddingTop = '0'; appWrapper.style.marginTop = '0'; }
            """)
            page.wait_for_timeout(500)

            # Take screenshot
            screenshot_bytes = page.screenshot(full_page=True, type="png")
            screenshot_b64 = base64.b64encode(screenshot_bytes).decode("utf-8")

            screenshots.append({
                "name": name,
                "screenshot_b64": screenshot_b64,
            })
            print(f"  [+] Captured ({len(screenshot_bytes) // 1024}KB)")

        browser.close()

    return screenshots


def render_html(config: dict, screenshots: list[dict]) -> str:
    """Render full HTML report using Jinja2 templates."""
    template_dir = Path(__file__).parent / "templates"
    env = Environment(loader=FileSystemLoader(str(template_dir)))

    now = datetime.now(IST)
    yesterday = now - timedelta(days=1)

    ctx = {
        "client_name": config["client_name"],
        "client_address": config.get("client_address", ""),
        "logo_url": config.get("logo_url", ""),
        "from_date": yesterday.strftime("%d %b %Y %I:%M %p"),
        "to_date": now.strftime("%d %b %Y %I:%M %p"),
        "generated_date": now.strftime("%d/%m/%Y"),
        "generated_time": now.strftime("%I:%M %p"),
        "sections": config.get("sections", []),
    }

    # Build pages
    cover_html = env.get_template("cover.html").render(**ctx)
    toc_html = env.get_template("toc.html").render(**ctx)

    section_tmpl = env.get_template("section.html")
    section_pages = ""
    for shot in screenshots:
        section_pages += section_tmpl.render(
            section_name=shot["name"],
            screenshot_b64=shot["screenshot_b64"],
        )

    # Combine into base template
    base_tmpl = env.get_template("base.html")
    content = cover_html + toc_html + section_pages
    full_html = base_tmpl.render(content=content, **ctx)

    return full_html


def html_to_pdf(html: str, gotenberg_url: str) -> bytes:
    """Convert HTML to PDF using Gotenberg."""
    url = f"{gotenberg_url}/forms/chromium/convert/html"

    footer_html = """<html><head><style>
    body { font-family: 'Segoe UI', Arial, sans-serif; font-size: 7px; color: #bdc3c7; width: 100%; margin: 0; padding: 0 24px; }
    .wrap { display: flex; justify-content: space-between; border-top: 1px solid #ecf0f1; padding-top: 4px; }
    .left { text-align: left; }
    .right { text-align: right; }
    </style></head><body>
    <div class="wrap"><span class="left">Confidential</span><span class="right">Page <span class="pageNumber"></span></span></div>
    </body></html>"""

    files = {
        "files": ("index.html", html.encode("utf-8"), "text/html"),
        "footer.html": ("footer.html", footer_html.encode("utf-8"), "text/html"),
    }
    data = {
        "landscape": "false",
        "printBackground": "true",
        "preferCssPageSize": "true",
        "marginTop": "0",
        "marginBottom": "0.6",
        "marginLeft": "0",
        "marginRight": "0",
        "paperWidth": "8.27",
        "paperHeight": "11.69",
    }

    print(f"[*] Converting to PDF via {url}")
    resp = requests.post(url, files=files, data=data, timeout=120)
    resp.raise_for_status()
    print(f"[+] PDF generated ({len(resp.content) // 1024}KB)")
    return resp.content


def send_email(config: dict, pdf_bytes: bytes):
    """Send PDF report via email."""
    email_cfg = config.get("email", {})
    if not email_cfg.get("to"):
        print("[!] No email recipients configured, skipping email")
        return

    now = datetime.now(IST)
    subject = email_cfg.get("subject", "{client_name} - Security Report - {date}").format(
        client_name=config["client_name"],
        date=now.strftime("%d/%m/%Y"),
    )

    msg = MIMEMultipart()
    msg["From"] = email_cfg["from_email"]
    msg["To"] = ", ".join(email_cfg["to"])
    msg["Subject"] = subject

    body = f"""
    <div style="font-family:Arial,sans-serif;max-width:600px;margin:0 auto">
        <h2 style="color:#1a1a2e;border-bottom:2px solid #14919B;padding-bottom:10px">
            Security Report - {config['client_name']}
        </h2>
        <p>Please find attached the daily security report.</p>
        <p style="color:#95a5a6;font-size:12px">
            Automatically generated on {now.strftime('%d %b %Y %I:%M %p')} IST
        </p>
    </div>
    """
    msg.attach(MIMEText(body, "html"))

    filename = f"security_report_{now.strftime('%Y%m%d')}.pdf"
    attachment = MIMEApplication(pdf_bytes, _subtype="pdf")
    attachment.add_header("Content-Disposition", "attachment", filename=filename)
    msg.attach(attachment)

    print(f"[*] Sending email to {email_cfg['to']}")
    with smtplib.SMTP(email_cfg["smtp_host"], email_cfg["smtp_port"]) as server:
        server.starttls()
        server.login(email_cfg["from_email"], email_cfg["password"])
        server.send_message(msg)
    print("[+] Email sent successfully")


def save_pdf(pdf_bytes: bytes, output_dir: str = "output"):
    """Save PDF to local output directory."""
    os.makedirs(output_dir, exist_ok=True)
    filename = f"security_report_{datetime.now(IST).strftime('%Y%m%d_%H%M')}.pdf"
    filepath = os.path.join(output_dir, filename)
    with open(filepath, "wb") as f:
        f.write(pdf_bytes)
    print(f"[+] PDF saved to {filepath}")
    return filepath


def main():
    parser = argparse.ArgumentParser(description="Wazuh Report Engine")
    parser.add_argument("--config", "-c", required=True, help="Path to client YAML config")
    parser.add_argument("--no-email", action="store_true", help="Skip sending email")
    parser.add_argument("--output", "-o", default="output", help="Output directory for PDF")
    args = parser.parse_args()

    config = load_config(args.config)
    print(f"\n{'='*50}")
    print(f"  Wazuh Report Engine")
    print(f"  Client: {config['client_name']}")
    print(f"  Time: {datetime.now(IST).strftime('%d %b %Y %I:%M %p')} IST")
    print(f"{'='*50}\n")

    # Step 1: Take screenshots
    screenshots = take_screenshots(config)
    print(f"\n[+] Captured {len(screenshots)} sections")

    # Step 2: Render HTML
    html = render_html(config, screenshots)
    print(f"[+] HTML rendered ({len(html) // 1024}KB)")

    # Step 3: Convert to PDF
    pdf_bytes = html_to_pdf(html, config["gotenberg_url"])

    # Step 4: Save locally
    filepath = save_pdf(pdf_bytes, args.output)

    # Step 5: Send email
    if not args.no_email:
        try:
            send_email(config, pdf_bytes)
        except Exception as e:
            print(f"[!] Email failed: {e}")

    print(f"\n[+] Report complete: {filepath}")


if __name__ == "__main__":
    main()
