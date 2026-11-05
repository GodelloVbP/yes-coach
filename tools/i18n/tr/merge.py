import json,glob,re
out={}
for f in sorted(glob.glob('/tmp/ex/tr/parts/*.tsv')):
    for line in open(f,encoding='utf-8'):
        line=line.rstrip('\n')
        if not line: continue
        k,v=line.split('\t',1)
        assert k.isdigit() and k not in out,(k,f)
        v=re.sub(r' ([?!:;])',lambda m:' '+m.group(1),v)
        v=v.replace('Yes Coach :','Yes Coach :')
        if v.startswith(' :'): pass
        out[k]=v
json.dump(out,open('/tmp/ex/tr/fr_ui.json','w',encoding='utf-8'),ensure_ascii=False,indent=0)
