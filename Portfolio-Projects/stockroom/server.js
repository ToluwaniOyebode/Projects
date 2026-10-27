import http from 'node:http';
import { readFile } from 'node:fs/promises';
import { mkdirSync } from 'node:fs';
import { dirname, resolve, sep, extname } from 'node:path';
import { fileURLToPath } from 'node:url';
import { Store, Problem } from './store.js';

const root=resolve(dirname(fileURLToPath(import.meta.url)),'static');
const dbPath=process.env.DB_PATH||resolve(root,'../data.sqlite3');mkdirSync(dirname(dbPath),{recursive:true});
const store=new Store(dbPath);const mime={'.html':'text/html','.js':'text/javascript','.css':'text/css','.svg':'image/svg+xml'};
const server=http.createServer(async(req,res)=>{
 const send=(status,body,type='application/json; charset=utf-8')=>{const buffer=Buffer.isBuffer(body)?body:Buffer.from(JSON.stringify(body));res.writeHead(status,{'Content-Type':type,'Content-Length':buffer.length,'X-Content-Type-Options':'nosniff','X-Frame-Options':'DENY','Cache-Control':'no-store','Content-Security-Policy':"default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; frame-ancestors 'none'; base-uri 'none'; form-action 'self'"});res.end(buffer)};
 try{
  const path=decodeURIComponent(new URL(req.url,'http://localhost').pathname);
  if(req.method==='GET'&&path==='/api/health')return send(200,{ok:true,project:'Stockroom'});
  if(!path.startsWith('/api/')){
   if(req.method!=='GET')throw new Problem('Method not allowed',405);
   const target=resolve(root,'.'+(path==='/'?'/index.html':path));if(!target.startsWith(root+sep))throw new Problem('Not found',404);
   let content;try{content=await readFile(target)}catch{throw new Problem('Not found',404)}
   return send(200,content,(mime[extname(target)]||'application/octet-stream')+'; charset=utf-8');
  }
  let body={};if(req.method==='POST'){
   if(req.headers.origin&&!['http://'+req.headers.host,'https://'+req.headers.host].includes(req.headers.origin))throw new Problem('Cross-origin writes are not allowed',403);
   if((req.headers['content-type']||'').split(';')[0]!=='application/json')throw new Problem('Use application/json',415);
   let raw='';let bytes=0;for await(const chunk of req){bytes+=chunk.length;if(bytes>1048576)throw new Problem('Request exceeds 1 MiB',413);raw+=chunk}
   try{body=JSON.parse(raw)}catch{throw new Problem('Invalid JSON')}
   if(!body||Array.isArray(body)||typeof body!=='object')throw new Problem('JSON body must be an object');
  }
  send(200,store.handle(req.method,path,body));
 }catch(error){if(!error.status)console.error(error);send(error.status||500,{error:error.status?error.message:'Internal server error; see server log'})}
});
server.listen(Number(process.env.PORT||8103),process.env.HOST||'127.0.0.1',()=>console.log(`Stockroom: http://${process.env.HOST||'127.0.0.1'}:${server.address().port}`));
for(const signal of ['SIGINT','SIGTERM'])process.on(signal,()=>server.close(()=>{store.close();process.exit(0)}));
