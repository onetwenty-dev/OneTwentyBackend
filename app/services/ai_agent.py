import os
import json
import boto3
from app.core.config import settings

def _get_bedrock_client():
    if settings.BEDROCK_API_KEY:
        # For Bedrock API Keys, we use the Bearer Token mechanism
        # Setting the environment variable is the recommended way for boto3 discovery
        os.environ["AWS_BEARER_TOKEN_BEDROCK"] = settings.BEDROCK_API_KEY
        return boto3.client(
            service_name="bedrock-runtime",
            region_name=settings.AWS_REGION,
        )
    return boto3.client(
        service_name="bedrock-runtime",
        region_name=settings.AWS_REGION,
        aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
        aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
    )

bedrock_runtime = _get_bedrock_client()

SYSTEM_PROMPT = """You are a knowledgeable and supportive diabetes care companion focused on helping people with Type 1 diabetes understand their CGM data and daily patterns.

Your tone is warm, calm, encouraging, and never judgmental. You speak like a supportive coach who also has strong clinical understanding of diabetes management.

Never shame the user. Celebrate progress and small wins.

REFERENCE CURRENT TIME will be provided with each message. Use it for ALL relative time parsing.

---

CONTEXT INFO (CGM USER):
- The user uses a Continuous Glucose Monitor (CGM).
- They have automatic glucose readings every 1-5 minutes.
- DO NOT act surprised or overly impressed by the volume of glucose data. It is automated and expected.
- Focus on patterns, trends, and the *impact* of events (food, insulin, exercise) rather than the mere existence of glucose readings.

---

TYPE 1 DIABETES CLINICAL BASELINES:
Use these standards when interpreting glucose patterns:
• Target Time In Range (70–180 mg/dL): **≥70%**
• Time Above Range (>180 mg/dL): **<25%**
• Time Below Range (<70 mg/dL): **<5%**
• Very Low (<54 mg/dL): should be **minimal or zero**

These are guidance benchmarks, not strict judgments. Encourage improvement rather than criticism.

---

CRITICAL ANALYSIS RULES:
Always consider **rate of change** and **event correlation**.
1. Look for **rapid rises or drops** (rate of change).
2. Correlate glucose with nearby events: carbs/meals, insulin doses, exercise.
3. Compare timestamps between glucose and events.
4. Explain likely causes when patterns align.

REPEATED PATTERN DETECTION:
If a food repeatedly causes large spikes for the user, mention that pattern.
Example: "It seems like upma tends to spike your glucose quickly."

---

UNEXPLAINED PATTERN HANDLING:
If glucose changes **without any logged events**, do NOT assume. 
Instead gently ask about: stress, illness, poor sleep, unlogged food, delayed digestion, or timing issues.
Stress is important: Psychological stress can **raise glucose levels**.

---

HISTORICAL DATA FORMAT:
• G:value@HH:mm → glucose reading
• C:value@HH:mm → carbs in grams
• I:value@HH:mm → insulin units
• E:mins@HH:mm → exercise minutes

---

YOUR PERSONALITY:
- Warm, conversational, and supportive.
- **Natural Flow**: Don't start every response with a formal greeting or a recap if it's already a continuous conversation.
- **Don't repeat yourself**: If you just acknowledged something in the previous message, move forward to the next step.
- Write the ai_response as natural flowing language — **not bullet points**.
- Keep responses concise but human.

---

EVENT LOGGING RULES:
1. ONLY extract events that the user explicitly reports in their **CURRENT USER MESSAGE**.
2. **NEVER** extract events from the "RECENT BIO-DATA SNAPSHOT" or "HISTORICAL DATA". Those are background data for reasoning only.
3. If the user refers to an old event (e.g., "Tell me about my 11:30 dose"), **DO NOT** log it again.
4. Possible extraction types: carb, insulin, exercise.
If the user mentions events without numbers, log them with notes (e.g., "Had a snack earlier").
Never invent numbers the user did not provide.

---

DATA RANGE TRANSPARENCY:
1. You MUST explicitly state the time range you are analyzing at the start of your response (e.g., "Analyzing your data since 11:00 AM today...").
2. If you are using the default 24-hour window because a specific time was not recognized, mention that clearly.

---

IMPORTANT - OUTPUT FORMAT:
You MUST return ONLY a valid JSON object. 
DO NOT include any text, greetings, or conversational filler BEFORE or AFTER the JSON.

REQUIRED JSON STRUCTURE:
{
  "extracted_events": [ 
    { "eventType": "carb", "carbs": 50, "local_time_string": "YYYY-MM-DD HH:mm:ss", "notes": "..." },
    { "eventType": "insulin", "insulin": 4, "local_time_string": "YYYY-MM-DD HH:mm:ss", "notes": "..." },
    { "eventType": "exercise", "duration": 20, "local_time_string": "YYYY-MM-DD HH:mm:ss", "notes": "..." }
  ],
  "ai_response": "Your warm, human response here."
}

If no data is loggable, extracted_events should be [].
"""

CLINICAL_SUMMARY_PROMPT = """You are a knowledgeable and supportive diabetes care companion helping someone with Type 1 diabetes interpret their CGM report.

Analyze the glucose data for the last {days} days and generate a concise clinical summary.

CLINICAL TARGETS:
• Time In Range (70–180 mg/dL): ≥70%
• Time Above Range (>180): <25%
• Time Below Range (<70): <5%

---

METRICS:
Average Glucose: {avg_glucose} mg/dL  
Time In Range: {tir}%  
Lows (<70): {low}%  
Very Lows (<54): {vlow}%  
Highs (>180): {high}%  
Estimated A1c (GMI): {gmi}%  
Glucose Variability (CV): {cv}%

---

INTERPRETATION GUIDELINES:
• Explain what these numbers mean for daily glucose stability.
• Mention variability if CV is elevated.
• Focus on **practical meaning**, not just numbers.
• Remain supportive and encouraging.

---

YOUR TASK:
1. Write a short **Clinical Brief** (2–3 sentences) explaining what the overall numbers suggest.
2. Identify one **Win** from the data.
3. Identify one **Focus Area** for the coming week.

Return ONLY a valid JSON object:
{
  "summary": "...",
  "win": "...",
  "focus_area": "..."
}
"""

class AIAgentService:
    @staticmethod
    def condense_data(entries: list, events: list, timezone_offset: int = 0) -> str:
        """
        Condenses SGV and Events into a TOON-like compact string.
        Smarter sampling: keeps all events, downsamples SGVs to show trends without hitting token limits.
        """
        import datetime
        import math
        
        # 1. Process SGV entries with sampling
        # We want at most ~80 SGV points to show a trend over any time period
        sgv_points = []
        if entries:
            step = max(1, math.ceil(len(entries) / 80))
            sampled_entries = entries[::step]
            for e in sampled_entries:
                sgv_points.append({'t': e['date'], 'v': f"G:{e['sgv']}"})
        
        # 2. Process all metabolic events (usually much fewer than SGVs)
        event_points = []
        for ev in events:
            etype = str(ev.get("eventType") or "Note").lower()
            notes = str(ev.get("notes", "")).lower()
            
            # Use local HH:mm for representation but store timestamp for sorting
            if any(k in etype for k in ["bolus", "insulin"]) or any(k in notes for k in ["insulin", "unit", "novorapid", "humalog", "fiasp", "apidra"]):
                val = ev.get("insulin") or 0
                if val > 0:
                    event_points.append({'t': ev['date'], 'v': f"I:{val}"})
            elif any(k in etype for k in ["meal", "carb", "snack"]) or any(k in notes for k in ["carb", "grams", "ate", "eat"]):
                val = ev.get("carbs") or 0
                if val > 0:
                    event_points.append({'t': ev['date'], 'v': f"C:{val}"})
            elif "exercise" in etype or any(k in notes for k in ["exercise", "walk", "run", "gym", "workout"]):
                val = ev.get("duration") or 0
                if val > 0:
                    event_points.append({'t': ev['date'], 'v': f"E:{val}m"})

        # 3. Handle data range info
        range_info = ""
        last_reading_info = ""
        if entries or events:
            all_ts = [x['t'] for x in sgv_points + event_points]
            if all_ts:
                start_dt = datetime.datetime.fromtimestamp(min(all_ts) / 1000, tz=datetime.timezone.utc) - datetime.timedelta(minutes=timezone_offset)
                end_dt = datetime.datetime.fromtimestamp(max(all_ts) / 1000, tz=datetime.timezone.utc) - datetime.timedelta(minutes=timezone_offset)
                range_info = f"Range: {start_dt.strftime('%b %d, %I:%M %p')} to {end_dt.strftime('%b %d, %I:%M %p')}"
                last_reading_info = f"Latest Reading: {end_dt.strftime('%I:%M %p')}"

        # 4. Combine and sort
        combined = sgv_points + event_points
        combined.sort(key=lambda x: x['t'])
        
        compact = []
        for item in combined:
            dt = datetime.datetime.fromtimestamp(item['t'] / 1000, tz=datetime.timezone.utc)
            local_dt = dt - datetime.timedelta(minutes=timezone_offset)
            # Use 24h format for internal tokens but the header uses 12h for clarity
            time_str = local_dt.strftime("%H:%M")
            compact.append(f"{item['v']}@{time_str}")
            
        final_str = ", ".join(compact)
        if range_info:
            final_str = f"[{range_info}] {final_str}"
        
        # Add explicit end marker to prevent AI from confusing history with future
        final_str += f" | {last_reading_info}"
            
        return final_str

    @staticmethod
    def _invoke_model_universal(system_prompt: str, messages: list, max_tokens: int = 1000, temperature: float = 0.5):
        """
        Universally handles Bedrock invocation for different model families (Anthropic, Amazon Nova).
        """
        model_id = settings.BEDROCK_MODEL_ID
        
        if "anthropic" in model_id:
            body = json.dumps({
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": max_tokens,
                "messages": messages,
                "system": system_prompt,
                "temperature": temperature,
                "top_p": 0.9
            })
        elif "nova" in model_id:
            # Nova expects content as a list of dictionaries with "text" key
            nova_messages = []
            for msg in messages:
                nova_messages.append({
                    "role": msg["role"],
                    "content": [{"text": msg["content"]}]
                })
            
            body = json.dumps({
                "system": [{"text": system_prompt}],
                "messages": nova_messages,
                "inferenceConfig": {
                    "maxTokens": max_tokens,
                    "temperature": temperature,
                    "topP": 0.9
                }
            })
        else:
            # Fallback/Generic (e.g. Llama 3)
            # This is a bit of a guess if it's not Nova or Anthropic, but 
            # let's keep it simple for now as the user requested Nova.
            raise ValueError(f"Unsupported model family: {model_id}")

        response = bedrock_runtime.invoke_model(
            body=body,
            modelId=model_id,
            accept="application/json",
            contentType="application/json"
        )
        response_body = json.loads(response.get('body').read())

        # Extract text based on family
        if "anthropic" in model_id:
            return response_body.get('content', [{}])[0].get('text', '')
        elif "nova" in model_id:
            return response_body.get('output', {}).get('message', {}).get('content', [{}])[0].get('text', '')
        
        return ""

    @staticmethod
    async def generate_clinical_summary(report_data: dict) -> dict:
        """
        Generates an AI-powered clinical summary based on report metrics.
        """
        metrics = report_data.get("metrics", {})
        days = metrics.get("days_covered", 7)
        tir = metrics.get("tir", {})
        
        prompt_text = CLINICAL_SUMMARY_PROMPT.format(
            days=days,
            avg_glucose=metrics.get("avg_glucose", 0),
            tir=tir.get("inRange", 0),
            low=tir.get("low", 0),
            vlow=tir.get("vlow", 0),
            high=tir.get("high", 0),
            gmi=metrics.get("gmi", 0),
            cv=metrics.get("cv", 0)
        )

        messages = [
            {"role": "user", "content": prompt_text}
        ]

        try:
            text_result = AIAgentService._invoke_model_universal(
                system_prompt="You are a helpful assistant that returns JSON.",
                messages=messages,
                max_tokens=500,
                temperature=0.2
            )
            
            import re
            json_match = re.search(r'(\{.*\})', text_result, re.DOTALL)
            if not json_match:
                raise ValueError("No JSON found in response")
            
            return json.loads(json_match.group(1))
        except Exception as e:
            print(f"Failed to generate AI summary: {e}")
            return {
                "summary": "Your glucose levels show steady patterns. Keep tracking to see more detailed insights soon!",
                "win": "Consistent logging of data.",
                "focus_area": "Continue monitoring trends after meals."
            }

    @staticmethod
    def _clean_json_string(json_str: str) -> str:
        """Fixes common LLM JSON errors like missing commas and trailing commas."""
        import re
        # 1. Remove comments
        json_str = re.sub(r'//.*?\n', '\n', json_str)
        json_str = re.sub(r'/\*.*?\*/', '', json_str, flags=re.DOTALL)
        
        # 2. Fix missing commas between top-level structural elements
        # Matches ] "key" or } "key" and adds a comma
        json_str = re.sub(r'([}\]])\s*(?=\")', r'\1, ', json_str)
        
        # 3. Fix double commas created by previous step (if one already existed)
        json_str = json_str.replace(', ,', ',')
        
        # 4. Remove trailing commas in arrays/objects (illegal in standard JSON)
        json_str = re.sub(r',\s*([}\]])', r'\1', json_str)
        
        return json_str

    @staticmethod
    def process_bedrock_chat(user_message: str, context_time_ms: int, health_context: str = "", doc_context: str = "", timezone_offset: int = 0, chat_history: list = None) -> dict:
        """
        Invokes model via Bedrock to parse events and generate responses.
        Includes chat history and continuous bio-data context.
        """
        import datetime
        from dateutil import parser
        
        # Calculate local reference for the prompt
        utc_now = datetime.datetime.fromtimestamp(context_time_ms / 1000, tz=datetime.timezone.utc)
        local_now = utc_now - datetime.timedelta(minutes=timezone_offset)
        
        current_iso_utc = utc_now.isoformat()
        current_iso_local = local_now.isoformat()

        system_content = SYSTEM_PROMPT + f"\n\nREFERENCE CURRENT TIME:\n- Server UTC: {current_iso_utc}\n- User Local: {current_iso_local}\n- Human Readable Today: {local_now.strftime('%A, %b %d, %Y %I:%M %p')}\n- Offset: {timezone_offset} mins\n"
        
        messages = []
        
        # 1. Add chat history if available (limit to last few turns to save tokens)
        if chat_history:
            for chat in chat_history[-5:]: # Use last 5 turns to stay within context windows effectively
                messages.append({"role": "user", "content": chat.get("userMessage", "")})
                messages.append({"role": "assistant", "content": chat.get("aiResponse", "")})

        # 2. Construct the current user message with context
        current_user_content = ""
        if health_context:
            current_user_content += f"RECENT BIO-DATA SNAPSHOT: {health_context}\n(Treatments like Insulin/Carbs are included here. Use this to determine Insulin on Board or active food.)\n\n"
        
        if doc_context:
            current_user_content += f"CLINICAL REPORTS KNOWLEDGE: {doc_context}\n\n"
            
        current_user_content += f"USER MESSAGE: {user_message}\n\n"
        current_user_content += "CRITICAL: Return ONLY JSON. No plain text outside structure."

        messages.append({"role": "user", "content": current_user_content})

        try:
            text_result = AIAgentService._invoke_model_universal(
                system_prompt=system_content,
                messages=messages,
                max_tokens=1000,
                temperature=0.1
            )
            
            # Find and parse JSON
            import re
            json_match = re.search(r'(\{.*\})', text_result, re.DOTALL)
            if not json_match:
                print(f"RAW RESULT FROM BEDROCK (No JSON found): {text_result}")
                raise ValueError("No JSON found in response")
            
            # Process with robust cleaning
            clean_json = AIAgentService._clean_json_string(json_match.group(1))
            result_dict = json.loads(clean_json, strict=False)
            
            # Post-process events: convert local_time_string to UTC Unix MS & ISO
            events = result_dict.get("extracted_events", [])
            for evt in events:
                local_str = evt.get("local_time_string")
                if local_str:
                    try:
                        # Parse the local time (it doesn't have TZ info yet)
                        dt_local = parser.parse(local_str)
                        # Construct a TD with the user's offset (UTC - Local)
                        # If offset is -330 (India), Local = UTC - (-330) = UTC + 330.
                        # So UTC = Local - 330 mins.
                        dt_utc = dt_local + datetime.timedelta(minutes=timezone_offset)
                        dt_utc = dt_utc.replace(tzinfo=datetime.timezone.utc)
                        
                        evt["date"] = int(dt_utc.timestamp() * 1000)
                        evt["dateString"] = dt_utc.isoformat().replace("+00:00", "Z")
                        # Clean up
                        del evt["local_time_string"]
                    except Exception as pe:
                        print(f"Failed to parse local_time_string '{local_str}': {pe}")
            
            return result_dict
                
        except Exception as e:
            text_result = locals().get('text_result', 'None')
            print(f"Bedrock Error or JSON Parsing Failed: {str(e)}\nRaw: {text_result}")
            # Raise the exception so the endpoint can decide not to save the chat history
            raise e
