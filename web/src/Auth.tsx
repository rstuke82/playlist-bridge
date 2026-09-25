import {Icon} from './Controls'
import {createContext,useContext,useEffect,useRef,useState} from 'react'
import App from './App'
import Brand from './Brand'
const Account=createContext<any>(null)
export const useAccount=()=>useContext(Account)
let csrf=''
let currentAccount:any=null
export const getAccount=()=>currentAccount
function acceptAccount(user:any){
 currentAccount=user
 if(!user)return
 const previous=localStorage.getItem('bridge-account-id')
 if(previous!==user.id){for(const key of Object.keys(localStorage)){if((key.startsWith('bridge-')||key.startsWith('playlist-bridge-'))&&key!=='playlist-bridge-appearance')localStorage.removeItem(key)}sessionStorage.clear()}
 localStorage.setItem('bridge-account-id',user.id)
}
const originalFetch=window.fetch.bind(window)
window.fetch=(input,init)=>{
 const url=new URL(typeof input==='string'?input:input instanceof URL?input.href:input.url,location.href)
 if(url.origin===location.origin&&url.pathname.startsWith('/api/')){
  const headers=new Headers(init?.headers||(input instanceof Request?input.headers:undefined))
  if(csrf)headers.set('X-Bridge-CSRF',csrf)
  return originalFetch(input,{...init,headers})
 }
 return originalFetch(input,init)
}
export default function Auth(){
 const [user,setUser]=useState<any>(null),[loading,setLoading]=useState(true),[error,setError]=useState(''),[waiting,setWaiting]=useState(false)
 const timer=useRef<ReturnType<typeof setTimeout>|undefined>(undefined),alive=useRef(true)
 useEffect(()=>{alive.current=true;fetch('/api/auth/me').then(r=>r.json()).then(d=>{csrf=d.csrf||'';acceptAccount(d.user);setUser(d.user)}).catch(()=>setError('Could not connect to Playlist Bridge.')).finally(()=>setLoading(false));return()=>{alive.current=false;clearTimeout(timer.current)}},[])
 async function login(){
  setError('');setWaiting(true)
  const popup=window.open('about:blank','plex-login','width=700,height=750')
  try{const r=await fetch('/api/auth/start',{method:'POST'});const d=await r.json();if(!r.ok)throw Error(d.detail);if(popup)popup.location.href=d.url;else throw Error('Allow pop-ups to sign in with Plex.')
   const deadline=Date.now()+600000
   const poll=async()=>{if(!alive.current)return;try{if(Date.now()>deadline)throw Error('Sign-in expired. Try again.');const r=await fetch('/api/auth/poll');const d=await r.json();if(!r.ok)throw Error(d.detail);if(d.user){csrf=d.csrf;acceptAccount(d.user);setUser(d.user);setWaiting(false);popup.close();return}timer.current=setTimeout(poll,2000)}catch(e:any){setError(e.message);setWaiting(false)}}
   timer.current=setTimeout(poll,2000)
  }catch(e:any){popup?.close();setError(e.message);setWaiting(false)}
 }
 if(loading)return <main><p>Loading Playlist Bridge…</p></main>
 if(!user)return <main className="login-panel panel"><Brand wordmark/><h1>Your music, connected.</h1><p>Sign in with your Plex account. You must have access to this server’s music library.</p>{error&&<p role="alert">{error}</p>}<button disabled={waiting} className="primary" onClick={login}>{waiting?'Waiting for Plex…':'Sign in with Plex'}</button><p className="muted">The server owner must sign in first. Managed Plex users are not supported.</p></main>
 return <Account.Provider value={user}><App/></Account.Provider>
}
export function AccountButton(){const user=useAccount();return <div className="account-menu"><span>{user?.name}</span><a href="#account" title="Your account settings"><Icon name="account"/> Account</a><button onClick={async()=>{await fetch('/api/auth/logout',{method:'POST'});sessionStorage.clear();location.hash='discover';location.reload()}}>Sign out</button></div>}

export function RequestAlbumLabel(){const user=useAccount();return <>{user?.admin?'Add Album to Lidarr':'Request Album'}</>}
