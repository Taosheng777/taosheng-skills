#!/usr/bin/env python3
"""Install the complete skill snapshot without changing model providers or credentials."""
from pathlib import Path
import argparse,datetime,hashlib,json,os,re,shutil,sys,tempfile
ROOT=Path(__file__).resolve().parents[1]
def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def load_bundle(root):
 root=root.resolve();m=json.loads((root/'environment-manifest.json').read_text());names=[x['name'] for x in m['skills']]
 if len(set(names))!=len(names):raise ValueError('重复技能名')
 for x in m['skills']:
  if not re.fullmatch(r'[a-z0-9][a-z0-9-]*',x['name']):raise ValueError('非法技能名')
  if x['path']!=f"plugins/taosheng-environment/skills/{x['name']}":raise ValueError('技能路径不符合清单')
 for name,h in m['files'].items():
  p=Path(name)
  if p.is_absolute() or '..' in p.parts:raise ValueError('清单路径越界')
  target=root/p
  if target.is_symlink() or not target.resolve().is_relative_to(root):raise ValueError('源文件链接越界')
  if not target.is_file() or digest(target)!=h:raise ValueError('文件摘要不匹配：'+name)
 for x in m['skills']:
  actual={p.relative_to(root).as_posix() for p in (root/x['path']).rglob('*') if p.is_file()}
  expected={p for p in m['files'] if p.startswith(x['path']+'/')}
  if actual!=expected:raise ValueError('技能文件清单不完整：'+x['name'])
 return m

def target_path(target,dest):
 if dest:return Path(dest).expanduser().resolve()
 if target=='auto':target='codex' if (Path.home()/'.codex').exists() else 'claude' if (Path.home()/'.claude').exists() else 'shared'
 return Path.home()/({'codex':'.codex','claude':'.claude','shared':'.agents'}[target])/'skills'

def same_tree(a,b):
 if a.is_symlink() or not a.is_dir():return False
 af={p.relative_to(a).as_posix():digest(p) for p in a.rglob('*') if p.is_file() and not p.is_symlink()}
 bf={p.relative_to(b).as_posix():digest(p) for p in b.rglob('*') if p.is_file()}
 return af==bf and not any(p.is_symlink() for p in a.rglob('*'))

def install(root,dest,replace=False):
 m=load_bundle(root);dest=Path(dest)
 if dest.is_symlink():raise ValueError('目标技能目录不能是符号链接')
 conflicts=[x['name'] for x in m['skills'] if (dest/x['name']).exists() and not same_tree(dest/x['name'],root/x['path']) or (dest/x['name']).is_symlink()]
 if conflicts and not replace:raise ValueError('已有不同版本，未修改任何技能。先备份审阅，确认后加 --replace：'+', '.join(conflicts))
 dest.mkdir(parents=True,exist_ok=True);staging=Path(tempfile.mkdtemp(prefix='.taosheng-stage-',dir=dest));backup=dest/'.taosheng-backups'/datetime.datetime.now().strftime('%Y%m%d-%H%M%S-%f');done=[];moved=[];copied=[]
 try:
  for x in m['skills']:
   if (dest/x['name']).exists() and same_tree(dest/x['name'],root/x['path']):continue
   shutil.copytree(root/x['path'],staging/x['name']);copied.append(x['name'])
  for name in copied:
   target=dest/name
   if target.exists() or target.is_symlink():
    backup.mkdir(parents=True,exist_ok=True);target.rename(backup/name);moved.append(name)
   (staging/name).rename(target);done.append(name)
  for x in m['skills']:
   assert (dest/x['name']/'SKILL.md').is_file(),x['name']
  state={'version':m['version'],'installed':[x['name'] for x in m['skills']],'changed':copied,'backup':str(backup) if moved else None}
  (dest/'.taosheng-install.json').write_text(json.dumps(state,ensure_ascii=False,indent=2)+'\n')
  return state
 except BaseException:
  for name in reversed(done):shutil.rmtree(dest/name)
  for name in reversed(moved):(backup/name).rename(dest/name)
  raise
 finally:shutil.rmtree(staging,ignore_errors=True)

def rules(root,path):
 path=Path(path).expanduser();begin='<!-- taosheng-environment:start -->';end='<!-- taosheng-environment:end -->';old=path.read_text() if path.exists() else ''
 if old.count(begin)!=old.count(end) or old.count(begin)>1:raise ValueError('规则标记不完整，未覆盖')
 snippet=begin+'\n'+(root/'templates/协作规则.md').read_text().strip()+'\n'+end
 new=re.sub(re.escape(begin)+r'[\s\S]*?'+re.escape(end),lambda _:snippet,old) if begin in old else old.rstrip()+'\n\n'+snippet+'\n'
 if new!=old:
  path.parent.mkdir(parents=True,exist_ok=True)
  if path.exists():shutil.copy2(path,path.with_name(path.name+'.taosheng-backup-'+datetime.datetime.now().strftime('%Y%m%d-%H%M%S-%f')))
  path.write_text(new)
 return str(path)

def doctor(root,dest):
 m=load_bundle(root);commands=['python3','node','git','uv','ffmpeg','markitdown','browser-harness','hithink-finance','agy','codebuddy','codex','claude']
 return {'skills_expected':len(m['skills']),'skills_installed':sum((dest/x['name']/'SKILL.md').is_file() for x in m['skills']),'commands':{c:bool(shutil.which(c)) for c in commands},'accounts':'未读取凭据。API Key、登录、官方插件权限需使用者本人配置。','runtime_setup':'ENVIRONMENT.md','external':m['external']}

def main():
 a=argparse.ArgumentParser();a.add_argument('--bundle',type=Path,default=ROOT);a.add_argument('--target',choices=['auto','codex','claude','shared'],default='auto');a.add_argument('--dest');a.add_argument('--replace',action='store_true');a.add_argument('--rules-file',type=Path);a.add_argument('--doctor',action='store_true');args=a.parse_args();root=args.bundle.resolve();dest=target_path(args.target,args.dest)
 try:
  if args.doctor:result=doctor(root,dest)
  else:
   result=install(root,dest,args.replace)
   if args.rules_file:result['rules']=rules(root,args.rules_file)
   result['readiness']=doctor(root,dest)
  print(json.dumps(result,ensure_ascii=False,indent=2))
 except (ValueError,AssertionError,OSError) as e:print(str(e),file=sys.stderr);return 1
 return 0
if __name__=='__main__':raise SystemExit(main())
