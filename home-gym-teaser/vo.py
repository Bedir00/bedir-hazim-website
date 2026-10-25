import json, subprocess, pathlib
T = pathlib.Path(__file__).parent
cfg = json.load(open(T/'scripts.json'))
out = T/'vo'; out.mkdir(exist_ok=True)
for key, c in cfg.items():
    for i, line in enumerate(c['vo']):
        f = out/f'{key}-{i}.wav'
        subprocess.run(['python3','-m','piper','-m',str(T/'voices/de_DE-thorsten-high.onnx'),'-f',str(f),'--length-scale','1.04','--sentence-silence','0.25'], input=line.encode(), check=True, capture_output=True)
        d = subprocess.run(['ffprobe','-v','error','-show_entries','format=duration','-of','csv=p=0',str(f)],capture_output=True,text=True).stdout.strip()
        print(key, i, d)
