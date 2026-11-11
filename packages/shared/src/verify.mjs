
// --- Prontidão SEM HRV (Health Connect): pesos recalibrados sono 40 / carga(TSB) 35 / ACWR 15 / mono 10 ---
const clampR=(x,a,b)=>Math.max(a,Math.min(b,x));
function sleepSubJS(hours,deep,rem){ let s=clampR(hours/8,0,1)*100; const frac=(deep+rem)/(hours*60); s+= frac>=0.35?5: frac<0.20?-8:0; return clampR(s,0,100); }
const tsbSubJS=(tsb,ctl)=>{const r=ctl>0?tsb/ctl:0;return r>=0?100:r>-0.15?85:r>-0.30?65:r>-0.50?45:25;};
const acwrSubJS=a=>(a>=0.8&&a<=1.3)?100:(a>1.3&&a<=1.5)?70:a>1.5?35:80;
// exemplo Lucas hoje: sono 6.5h (deep52/rem6), TSB -128, CTL ~176, ACWR 1.7, overreaching
const ss=sleepSubJS(6.5,52,6), st=tsbSubJS(-128,176), sa=acwrSubJS(1.7), sm=100;
let sc=ss*0.40+st*0.35+sa*0.15+sm*0.10; sc=Math.min(sc,45); // trava overreaching
console.log("");
console.log("Prontidão SEM HRV (dia de overreaching):", Math.round(sc), "→", (sc>=75?"verde":sc>=60?"verde-":sc>=45?"amarelo":"vermelho"));
console.log("  sono_sub=",Math.round(ss)," tsb_sub=",st," acwr_sub=",sa);
