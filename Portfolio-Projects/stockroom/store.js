import { DatabaseSync } from 'node:sqlite';

export class Problem extends Error { constructor(message,status=400){super(message);this.status=status} }
export function text(value,name,max=120){if(typeof value!=='string'||!value.trim()||value.trim().length>max)throw new Problem(`${name} must contain 1–${max} characters`);return value.trim()}
export function integer(value,name,min=0,max=1000000){if(!Number.isSafeInteger(value)||value<min||value>max)throw new Problem(`${name} must be an integer from ${min} to ${max}`);return value}

export class Store {
 constructor(path='data.sqlite3',demo=true){
  this.db=new DatabaseSync(path,{timeout:10000});
  this.db.exec(`PRAGMA journal_mode=WAL; PRAGMA foreign_keys=ON;
   CREATE TABLE IF NOT EXISTS products(sku TEXT PRIMARY KEY,name TEXT NOT NULL,on_hand INTEGER NOT NULL CHECK(on_hand>=0),reorder_point INTEGER NOT NULL CHECK(reorder_point>=0),unit_price_cents INTEGER NOT NULL CHECK(unit_price_cents>=0));
   CREATE TABLE IF NOT EXISTS reservations(id INTEGER PRIMARY KEY,sku TEXT NOT NULL REFERENCES products(sku),quantity INTEGER NOT NULL CHECK(quantity>0),status TEXT NOT NULL CHECK(status IN ('held','shipped','released')),request_key TEXT NOT NULL UNIQUE,created_at TEXT DEFAULT(strftime('%Y-%m-%dT%H:%M:%fZ','now')));
   CREATE INDEX IF NOT EXISTS reservation_sku_status ON reservations(sku,status);
   CREATE TABLE IF NOT EXISTS movements(id INTEGER PRIMARY KEY,sku TEXT NOT NULL REFERENCES products(sku),kind TEXT NOT NULL,quantity INTEGER NOT NULL,note TEXT NOT NULL,created_at TEXT DEFAULT(strftime('%Y-%m-%dT%H:%M:%fZ','now')));
   CREATE TABLE IF NOT EXISTS metadata(key TEXT PRIMARY KEY);`);
  if(demo&&!this.db.prepare("SELECT 1 FROM metadata WHERE key='seeded'").get())this.transaction(()=>{
   const insert=this.db.prepare('INSERT OR IGNORE INTO products VALUES(?,?,?,?,?)');
   for(const p of [['KEY-01','Mechanical keyboard',32,10,4200000],['HUB-02','USB-C multiport hub',7,8,1850000],['MOU-03','Wireless mouse',48,12,1250000],['MON-04','27-inch monitor',12,4,21000000],['PAD-05','Desk mat',4,6,850000],['CAM-06','HD webcam',21,5,3200000]])insert.run(...p);
   this.db.prepare("INSERT INTO metadata VALUES('seeded')").run();
  });
 }
 close(){this.db.close()}
 transaction(fn){this.db.exec('BEGIN IMMEDIATE');try{const result=fn();this.db.exec('COMMIT');return result}catch(error){this.db.exec('ROLLBACK');throw error}}
 products(){return this.db.prepare(`SELECT p.*,coalesce((SELECT sum(quantity) FROM reservations r WHERE r.sku=p.sku AND r.status='held'),0) reserved, p.on_hand-coalesce((SELECT sum(quantity) FROM reservations r WHERE r.sku=p.sku AND r.status='held'),0) available FROM products p ORDER BY p.sku`).all()}
 product(sku){const p=this.products().find(p=>p.sku===sku);if(!p)throw new Problem('Product not found',404);return p}
 createProduct(data){
  const sku=text(data.sku,'sku',32).toUpperCase();if(!/^[A-Z0-9_-]+$/.test(sku))throw new Problem('sku may contain letters, numbers, _ and -');
  const name=text(data.name,'name');const on_hand=integer(data.on_hand,'on_hand');const reorder_point=integer(data.reorder_point,'reorder_point');const price=integer(data.unit_price_cents,'unit_price_cents',0,1000000000);
  return this.transaction(()=>{if(this.db.prepare('SELECT 1 FROM products WHERE sku=?').get(sku))throw new Problem('SKU already exists',409);this.db.prepare('INSERT INTO products VALUES(?,?,?,?,?)').run(sku,name,on_hand,reorder_point,price);this.movement(sku,'opening',on_hand,'Opening stock');return this.product(sku)});
 }
 movement(sku,kind,quantity,note){this.db.prepare('INSERT INTO movements(sku,kind,quantity,note) VALUES(?,?,?,?)').run(sku,kind,quantity,note)}
 reserve(data){
  const sku=text(data.sku,'sku',32);const quantity=integer(data.quantity,'quantity',1);const key=text(data.request_key,'request_key',100);
  return this.transaction(()=>{
   const previous=this.db.prepare('SELECT * FROM reservations WHERE request_key=?').get(key);
   if(previous){if(previous.sku!==sku||previous.quantity!==quantity)throw new Problem('Idempotency key already used for different input',409);return {...previous,replayed:true}}
   const p=this.product(sku);if(p.available<quantity)throw new Problem(`Only ${p.available} units are available`,409);
   const result=this.db.prepare("INSERT INTO reservations(sku,quantity,status,request_key) VALUES(?,?,'held',?)").run(sku,quantity,key);
   this.movement(sku,'reserve',quantity,`Reservation #${result.lastInsertRowid}`);
   return {...this.db.prepare('SELECT * FROM reservations WHERE id=?').get(Number(result.lastInsertRowid)),replayed:false};
  });
 }
 transition(id,target){
  integer(id,'id',1);if(!['shipped','released'].includes(target))throw new Problem('Invalid transition');
  return this.transaction(()=>{
   const row=this.db.prepare('SELECT * FROM reservations WHERE id=?').get(id);if(!row)throw new Problem('Reservation not found',404);
   if(row.status===target)return {...row,replayed:true};
   if(row.status!=='held')throw new Problem(`Reservation is already ${row.status}`,409);
   if(target==='shipped')this.db.prepare('UPDATE products SET on_hand=on_hand-? WHERE sku=?').run(row.quantity,row.sku);
   this.db.prepare('UPDATE reservations SET status=? WHERE id=?').run(target,id);
   this.movement(row.sku,target==='shipped'?'ship':'release',row.quantity,`Reservation #${id}`);
   return {...row,status:target,replayed:false};
  });
 }
 adjust(sku,data){
  const delta=integer(data.delta,'delta',-1000000,1000000);if(delta===0)throw new Problem('delta must be non-zero');const note=text(data.note,'note',300);
  return this.transaction(()=>{const p=this.product(sku);if(p.on_hand+delta<p.reserved)throw new Problem('Adjustment would consume reserved stock',409);if(p.on_hand+delta>1000000)throw new Problem('Stock limit is 1,000,000');this.db.prepare('UPDATE products SET on_hand=on_hand+? WHERE sku=?').run(delta,sku);this.movement(sku,'adjust',delta,note);return this.product(sku)});
 }
 reservations(){return this.db.prepare('SELECT r.*,p.name FROM reservations r JOIN products p USING(sku) ORDER BY r.id DESC LIMIT 100').all()}
 movements(){return this.db.prepare('SELECT * FROM movements ORDER BY id DESC LIMIT 50').all()}
 stats(){const p=this.products();return {products:p.length,available:p.reduce((s,p)=>s+p.available,0),reserved:p.reduce((s,p)=>s+p.reserved,0),low_stock:p.filter(p=>p.available<=p.reorder_point).length,value_cents:p.reduce((s,p)=>s+p.on_hand*p.unit_price_cents,0)}}
 handle(method,path,body){
  if(method==='GET'&&path==='/api/products')return this.products();
  if(method==='POST'&&path==='/api/products')return this.createProduct(body);
  if(method==='GET'&&path==='/api/stats')return this.stats();
  if(method==='GET'&&path==='/api/reservations')return this.reservations();
  if(method==='POST'&&path==='/api/reservations')return this.reserve(body);
  if(method==='GET'&&path==='/api/movements')return this.movements();
  const action=path.match(/^\/api\/reservations\/(\d+)\/(ship|release)$/);
  if(method==='POST'&&action)return this.transition(Number(action[1]),action[2]==='ship'?'shipped':'released');
  const adjust=path.match(/^\/api\/products\/([^/]+)\/adjust$/);
  if(method==='POST'&&adjust)return this.adjust(adjust[1],body);
  throw new Problem('Not found',404);
 }
}
