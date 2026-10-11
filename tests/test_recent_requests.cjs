const fs=require('fs'),vm=require('vm'),assert=require('node:assert/strict'),ts=require('../web/node_modules/typescript');
function load(file,imports={}){const module={exports:{}};const code=ts.transpileModule(fs.readFileSync('web/src/'+file,'utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS,jsx:ts.JsxEmit.ReactJSX,target:ts.ScriptTarget.ES2022}}).outputText;vm.runInNewContext(code,{exports:module.exports,require:n=>imports[n]||{},console});return module.exports}
const presentation=load('requestPresentation.ts'),covers=load('AlbumCover.tsx',{'./requestPresentation':presentation});
for(const row of [{status:'queued'},{status:'approval'},{status:'adding'},{status:'search_pending',error:'command still started after 120s'},{status:'search_completed'}])assert.equal(presentation.downloadGroup(row),'In Progress');
assert.equal(covers.coverStatus({status:'queued',availability:'Unknown'}).label,'Queued');
assert.equal(covers.coverStatus({status:'search_pending',error:'command still started after 120s'}).tone,'progress');
assert.equal(covers.coverStatus({status:'search_completed',download_status:'Imported into Lidarr'}).label,'Waiting for Plex');
for(const row of [{status:'search_failed'},{status:'search_unknown'},{status:'search_pending',download_error:'Import failed'},{status:'search_pending',downloads:[{error:'Corrupt file'}]}])assert.equal(presentation.downloadGroup(row),'Needs Action');
const jsx=(type,props)=>({type,props});const shelves=load('DiscoverShelves.tsx',{'react/jsx-runtime':{jsx,jsxs:jsx},'./AlbumCover':covers});
const tree=shelves.RecentRequestCard({row:{key:'album',title:'Album name',artist:'Artist',year:2004,artwork:'https://example.org/cover.jpg',status:'queued',requesters:[{user_id:'u',name:'User',avatar:'https://example.org/user.jpg'}]}});
function walk(n,fn){if(!n||typeof n!=='object')return;fn(n);for(const c of [n.props?.children].flat(Infinity))walk(c,fn)}
const classes=[],texts=[];walk(tree,n=>{if(n.props?.className)classes.push(n.props.className);for(const c of [n.props?.children].flat(Infinity))if(typeof c==='string')texts.push(c)});
assert.equal(tree.props.href,'#requests/album');assert(classes.includes('recent-request-copy'));assert(classes.includes('recent-request-art'));assert(texts.includes('User'));assert(texts.includes('Queued'));assert(!texts.includes('2004'));
console.log('Recent request lifecycle and card rendering checks passed');
