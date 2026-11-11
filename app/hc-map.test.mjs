const minBetween=(a,b)=>Math.max(0,Math.round((new Date(b)-new Date(a))/60000));
function mapType(t){t=(t||"").toUpperCase();if(t.includes("RUN")||t.includes("WALK"))return"Corrida";if(t.includes("BIK")||t.includes("CYCL"))return"Bike";if(t.includes("SWIM"))return"Natação";if(t.includes("STRENGTH")||t.includes("WEIGHT"))return"Força";return"Outro";}
function activitiesFromHC(sessions,hr){return sessions.map((se,i)=>{const start=+new Date(se.startTime),end=+new Date(se.endTime);const win=hr.filter(h=>{const t=+new Date(h.time);return t>=start&&t<=end;}).map(h=>h.beatsPerMinute);const a={id:se.metadata?.id||`hc-${i}`,sport:mapType(se.exerciseType),date:se.startTime.slice(0,10),durationMin:minBetween(se.startTime,se.endTime)};if(win.length){a.avgHr=Math.round(win.reduce((s,x)=>s+x,0)/win.length);a.maxHr=Math.max(...win);}return a;});}
function wellnessFromHC(date,sleep){const w={date};if(sleep){w.sleepHours=minBetween(sleep.startTime,sleep.endTime)/60;const st=n=>(sleep.stages||[]).filter(s=>s.stage.toLowerCase().includes(n)).reduce((x,s)=>x+minBetween(s.startTime,s.endTime),0);const d=st("deep"),r=st("rem");if(d)w.sleepDeepMin=d;if(r)w.sleepRemMin=r;}return w;}

const sessions=[
 {startTime:"2026-07-28T10:35:00Z",endTime:"2026-07-28T11:14:00Z",exerciseType:"STRENGTH_TRAINING"},
 {startTime:"2026-07-28T17:05:00Z",endTime:"2026-07-28T17:50:00Z",exerciseType:"BIKING"}
];
const hr=[{time:"2026-07-28T17:10:00Z",beatsPerMinute:140},{time:"2026-07-28T17:30:00Z",beatsPerMinute:146},{time:"2026-07-28T17:45:00Z",beatsPerMinute:178}];
const sleep={startTime:"2026-07-27T23:30:00Z",endTime:"2026-07-28T06:00:00Z",stages:[{stage:"deep",startTime:"2026-07-27T23:40:00Z",endTime:"2026-07-28T00:32:00Z"},{stage:"rem",startTime:"2026-07-28T05:00:00Z",endTime:"2026-07-28T05:06:00Z"}]};
console.log("Activities:", JSON.stringify(activitiesFromHC(sessions,hr),null,1));
console.log("Wellness:", JSON.stringify(wellnessFromHC("2026-07-28",sleep),null,1));
