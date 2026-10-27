/** Real browser acceptance tests. Run: npm install && npx playwright install chromium && npm run test:browser */
import { chromium } from 'playwright';
import assert from 'node:assert/strict';
import { spawn } from 'node:child_process';
import { mkdir, mkdtemp, rm, writeFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join, dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const root=resolve(dirname(fileURLToPath(import.meta.url)),'..');
const projects=['applyboard','ledgerlens','stockroom','signaldesk','pitchside','queuecraft'];
const tmp=await mkdtemp(join(tmpdir(),'portfolio-browser-'));
const output=join(root,'artifacts');await mkdir(join(output,'screenshots'),{recursive:true});
const children=[];const reports=[];let browser;
const until=async fn=>{for(let i=0;i<150;i++){if(await fn())return;await new Promise(r=>setTimeout(r,100))}throw new Error('Condition did not become true')};
const text=async(page,selector)=>page.locator(selector).innerText();
try{
 browser=await chromium.launch({headless:true});
 for(const [i,slug]of projects.entries()){
  const port=18101+i,base=`http://127.0.0.1:${port}`;
  const child=spawn(slug==='stockroom'?'node':(process.env.PYTHON||'python'),[slug==='stockroom'?'server.js':'server.py'],{cwd:join(root,slug),env:{...process.env,PORT:String(port),DB_PATH:join(tmp,slug+'.db')},stdio:['ignore','pipe','pipe']});children.push(child);let logs='';child.stdout.on('data',d=>logs+=d);child.stderr.on('data',d=>logs+=d);
  await until(async()=>{if(child.exitCode!==null)throw new Error(logs);try{return (await fetch(base+'/api/health')).ok}catch{return false}});
  const page=await browser.newPage({viewport:{width:1440,height:1000}});const errors=[];
  page.on('pageerror',e=>errors.push(e.message));page.on('console',m=>{if(m.type()==='error')errors.push(m.text())});
  await page.goto(base);await page.locator('#stats .stat').first().waitFor();assert.equal(await page.locator('#stats .stat').count(),4);
  await page.screenshot({path:join(output,'screenshots',slug+'-desktop.png'),fullPage:true});
  await page.setViewportSize({width:390,height:844});await page.screenshot({path:join(output,'screenshots',slug+'-mobile.png'),fullPage:true});
  assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth+1),slug+' overflows mobile viewport');
  await page.setViewportSize({width:1440,height:1000});
  if(slug==='applyboard'){
   await page.getByRole('button',{name:'Add application'}).click();await page.getByLabel('Company',{exact:true}).fill('Browser Fixture');await page.getByLabel('Role',{exact:true}).fill('Test Engineer');await page.getByRole('button',{name:'Save application'}).click();await until(async()=>(await text(page,'#board')).includes('Browser Fixture'));
   const card=page.locator('.card').filter({hasText:'Browser Fixture'});await card.locator('select').selectOption('interview');await until(async()=>(await text(page,'.lane:has(.lane-title :text("interview"))')).includes('Browser Fixture'));
  }else if(slug==='ledgerlens'){
   await page.getByRole('button',{name:'Add expense'}).click();await page.getByLabel('Description',{exact:true}).fill('Browser fixture expense');await page.getByLabel('Amount (NGN)',{exact:true}).fill('123.45');await page.getByRole('button',{name:'Save entry'}).click();await until(async()=>(await text(page,'#rows')).includes('Browser fixture expense'));
   await page.getByLabel('Monthly limit (NGN)',{exact:true}).fill('25000');await page.getByRole('button',{name:'Save budget'}).click();await until(async()=>(await text(page,'#toast')).includes('Budget updated'));
  }else if(slug==='stockroom'){
   await page.getByLabel('Product',{exact:true}).selectOption('KEY-01');await page.getByLabel('Quantity',{exact:true}).fill('2');await page.getByRole('button',{name:'Reserve units'}).click();await until(async()=>(await text(page,'#reservations')).includes('held'));
   await page.getByRole('button',{name:'Ship',exact:true}).first().click();await until(async()=>(await text(page,'#reservations')).includes('shipped'));
   assert.match(await text(page,'#products'),/Mechanical keyboard/);
  }else if(slug==='signaldesk'){
   await page.getByRole('button',{name:'Add document'}).click();await page.getByLabel('Document title').fill('Browser fixture document');await page.getByLabel('Content',{exact:true}).fill('# Source\nA browserneedle belongs in a searchable passage.');await page.getByRole('button',{name:'Save & index'}).click();await until(async()=>(await text(page,'#documents')).includes('Browser fixture document'));
   await page.getByLabel('Search the knowledge base').fill('browserneedle');await page.getByRole('button',{name:'Search ↗',exact:true}).click();await until(async()=>(await text(page,'#results')).includes('Browser fixture document'));await page.locator('.result details summary').first().click();assert.match(await text(page,'.result details'),/browserneedle/);
  }else if(slug==='pitchside'){
   await page.getByLabel('Team',{exact:true}).selectOption('Harbor FC');await page.getByRole('button',{name:'Apply filters'}).click();await until(async()=>!(await text(page,'#events')).includes('Atlas United'));
   await page.getByRole('button',{name:'Shots',exact:true}).click();assert.equal(await text(page,'#pitch-title'),'Shot locations');assert.ok(await page.locator('#pitch svg circle').count()>2);
  }else if(slug==='queuecraft'){
   await page.getByLabel('Task type').selectOption('flaky');await page.getByLabel('Payload (JSON)').fill('{"fail_until": 2}');await page.getByLabel('Max attempts').fill('1');await page.getByRole('button',{name:'Enqueue job'}).click();await until(async()=>(await text(page,'#jobs')).includes('dead'));
   await page.getByRole('button',{name:'Inspect',exact:true}).first().click();assert.match(await text(page,'#detail'),/Demonstration transient failure/);await page.getByRole('button',{name:'Close',exact:true}).click();await page.getByRole('button',{name:'Retry',exact:true}).first().click();await until(async()=>(await text(page,'#toast')).includes('returned to queue'));
  }
  assert.deepEqual(errors,[],slug+' browser errors');reports.push({project:slug,desktop:true,mobile:true,workflow:true,consoleErrors:errors});await page.close();console.log(`Browser acceptance passed: ${slug}`);
 }
 await writeFile(join(output,'browser-report.json'),JSON.stringify({projects:reports},null,2));
}catch(error){await writeFile(join(output,'browser-report.json'),JSON.stringify({projects:reports,error:error.message},null,2));throw error}
finally{
 if(browser)await browser.close();
 for(const child of children)child.kill('SIGTERM');
 await Promise.all(children.map(child=>child.exitCode===null?new Promise(r=>{child.once('exit',r);setTimeout(()=>{child.kill('SIGKILL');r()},3000)}):null));
 await rm(tmp,{recursive:true,force:true});
}
