const K_CTL = 1 - Math.exp(-1/42), K_ATL = 1 - Math.exp(-1/7);
const clamp=(x,a,b)=>Math.max(a,Math.min(b,x));
function trimp(sex,hrRest,hrMax,dur,avgHr){const hrr=clamp((avgHr-hrRest)/(hrMax-hrRest),0,1);const Y=sex==="F"?0.86*Math.exp(1.67*hrr):0.64*Math.exp(1.92*hrr);return dur*hrr*Y;}
const load = trimp("M",68,188,45,154);
const ctl0=65,atl0=70;
const ctl=ctl0*(1-K_CTL)+load*K_CTL, atl=atl0*(1-K_ATL)+load*K_ATL, tsb=ctl0-atl0;
console.log("Exemplo (corrida 45min, FC 154, FCmax 188, rep 68, homem):");
console.log("  TRIMP session_load =", load.toFixed(1), "(esperado ~82)");
console.log("  K_CTL =", K_CTL.toFixed(5), " K_ATL =", K_ATL.toFixed(5));
console.log("  CTL =", ctl.toFixed(1), " ATL =", atl.toFixed(1), " TSB =", tsb.toFixed(1));

// --- Prontidão SEM HRV (Health Connect): sono 40 / carga(TSB) 35 / ACWR 15 / mono 10 ---
const clampR=(x,a,b)=>Math.max(a,Math.min(b,x));
function sleepSubJS(h,deep,rem){let s=clampR(h/8,0,1)*100;const frac=(deep+rem)/(h*60);s+=frac>=0.35?5:frac<0.20?-8:0;return clampR(s,0,100);}
const tsbSubJS=(tsb,ctl)=>{const r=ctl>0?tsb/ctl:0;return r>=0?100:r>-0.15?85:r>-0.30?65:r>-0.50?45:25;};
const acwrSubJS=a=>(a>=0.8&&a<=1.3)?100:(a>1.3&&a<=1.5)?70:a>1.5?35:80;
const ss=sleepSubJS(6.5,52,6), st=tsbSubJS(-128,176), sa=acwrSubJS(1.7), sm=100;
let sc=ss*0.40+st*0.35+sa*0.15+sm*0.10; sc=Math.min(sc,45);
console.log("");
console.log("Prontidão SEM HRV (dia de overreaching):", Math.round(sc), "->", (sc>=75?"verde":sc>=60?"verde-":sc>=45?"amarelo":"vermelho"));
console.log("  sono_sub=",Math.round(ss)," tsb_sub=",st," acwr_sub=",sa);
