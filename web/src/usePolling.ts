import { useEffect, useRef } from 'react'

// Schedule after completion, never on an interval. A wake replaces the timer.
export function usePolling(task:()=>Promise<void>, delay:()=>number, event:string) {
  const latest=useRef({task,delay});latest.current={task,delay}
  useEffect(()=>{
    let stopped=false, generation=0, timer:ReturnType<typeof setTimeout>|undefined
    let running:Promise<void>|undefined
    async function tick(){
      const ticket=++generation
      clearTimeout(timer)
      if(!running) running=latest.current.task().catch(()=>{}).finally(()=>{running=undefined})
      await running
      if(!stopped && ticket===generation) timer=setTimeout(tick,latest.current.delay())
    }
    const wake=()=>{void tick()}
    window.addEventListener(event,wake)
    void tick()
    return ()=>{stopped=true;++generation;clearTimeout(timer);window.removeEventListener(event,wake)}
  },[event])
}
