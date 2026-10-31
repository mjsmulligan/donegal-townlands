import csv,json
import sys,pathlib
ROOT=pathlib.Path(__file__).resolve().parent.parent
D=str(ROOT/'data'/'census')+'/'
# usage: python tools/extract_census.py   (writes townlands/cullionboy/records/census.json)
def L(f): return list(csv.DictReader(open(D+f,encoding='utf-8')))
def num(v):
    try: return int(float(v))
    except: return None
out={}
for y,f in((1901,'1901_Clogher.csv'),(1911,'1911_Clogher.csv')):
    r=[x for x in L(f) if x['townland']=='Cullionboy']
    out[str(y)]=[{'h':num(x['house_number']),'s':x['surname'],'f':x['firstname'],'a':num(x['age']),'x':x['sex'],'r':x['relation_to_head_updated'],'m':x['marriage_status'],'o':x['occupation_updated'],'i':1 if 'Irish' in x['language_updated'] else 0} for x in r]
r=[x for x in L('1926_Clogher.csv') if x['townland']=='Collinboy']
rows=[]
for x in r:
    fo=x['aform_name'].split('_')[3]
    cl=x['children_living']
    m=x['updated_marriage'] or ((cl+' children living') if cl.isdigit() else '')
    rows.append({'h':'0017' if fo=='0016' else fo,'fo':fo,'s':x['surname'],'f':x['first_name'],'a':num(x['updated_age']),'x':x['updated_sex'],'r':x['updated_relationship_to_head'] or x['relationship_to_head'],'m':m,'o':'','i':1 if 'Irish' in x['updated_irish_language'] else 0})
rows.sort(key=lambda z:z['fo'])
out['1926']=rows
json.dump(out,open(ROOT/'townlands/cullionboy/records/census.json','w'),ensure_ascii=False,separators=(',',':'))
print({k:len(v) for k,v in out.items()})
