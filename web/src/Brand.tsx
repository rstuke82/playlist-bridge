/** Small-size version of the musical-note bridge mark. */
export default function Brand({wordmark=false}:{wordmark?:boolean}){
 return <span className={`bridge-brand ${wordmark?'with-wordmark':''}`}><svg className="bridge-logo" viewBox="0 0 64 64" role="img" aria-label={wordmark?undefined:'Playlist Bridge'} aria-hidden={wordmark||undefined}><path fill="currentColor" d="M17 12a4 4 0 0 1 8 0v12c8-6 16-6 24 0V12a4 4 0 0 1 8 0v34c0 8-6 13-13 13-6 0-10-4-10-9s5-10 11-10h4v-7c-8-7-16-7-24 0v13c0 8-6 13-13 13C6 59 2 55 2 50s5-10 11-10h4Z"/></svg>{wordmark&&<span>Playlist Bridge</span>}</span>
}
