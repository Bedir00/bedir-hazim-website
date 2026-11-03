import base64, json, urllib.request, sys, time, subprocess, os
def tts(text, voice, out, model="gemini-3.8-flash-tts"):
    body = {"contents":[{"parts":[{"text":text}]}],
            "generationConfig":{"responseModalities":["AUDIO"],"speechConfig":{"voiceConfig":{"prebuiltVoiceConfig":{"voiceName":voice}}}}}
    for attempt in range(5):
        req = urllib.request.Request(f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
            data=json.dumps(body).encode(), headers={"Content-Type":"application/json","x-goog-api-key":"dummy"})
        try:
            r = json.load(urllib.request.urlopen(req, timeout=180))
            p = r["candidates"][0]["content"]["parts"][0]["inlineData"]
            raw = base64.b64decode(p["data"]); mt = p["mimeType"]
            if "wav" in mt:
                open(out, "wb").write(raw)
            else:
                rate = 24000
                if "rate=" in mt: rate = int(mt.split("rate=")[1].split(";")[0])
                open(out + ".pcm", "wb").write(raw)
                subprocess.run(["ffmpeg","-v","error","-y","-f","s16le","-ar",str(rate),"-ac","1","-i",out+".pcm",out],check=True)
                os.remove(out + ".pcm")
            return True
        except Exception as ex:
            msg = getattr(ex,'read',lambda:b'')()[:200]
            print("retry", voice, ex, msg, file=sys.stderr); time.sleep(6 * (attempt + 1))
    return False
if __name__ == "__main__":
    text, voice, out = sys.argv[1], sys.argv[2], sys.argv[3]
    model = sys.argv[4] if len(sys.argv) > 4 else "gemini-3.8-flash-tts"
    print(out, tts(text, voice, out, model))
