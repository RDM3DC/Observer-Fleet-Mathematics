#!/usr/bin/env python3
"""
Fleet-EGATL compact runner

Missions:
  1: recover a damaged phase-memory signal
  2: search for a Holonomy Scar Lantern candidate
  3: test a candidate knot memory fingerprint

Run:
  pip install -r requirements.txt
  python fleet_egatl_complete.py --mission all

Research status: toy scaffold, not a proof of new physics or knot theory.
"""

import argparse, json
from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt


def mkdir(p):
    p = Path(p)
    p.mkdir(parents=True, exist_ok=True)
    return p


def base(th, harmonic=2.7, amp=0.35):
    return np.sin(th) + amp * np.sin(harmonic * th)


def robust_weight(r, strength=5.0):
    scale = np.median(np.abs(r - np.median(r))) + 1e-9
    return 1.0 / (1.0 + (np.abs(r) / (strength * scale)) ** 2)


def memory_word(t, residual, damage=None, scar=None, chunks=22):
    if damage is None:
        damage = np.zeros_like(residual, dtype=bool)
    if scar is None:
        scar = np.zeros_like(residual, dtype=bool)
    dr = np.gradient(residual, t)
    out = []
    for idx in np.array_split(np.arange(len(t)), chunks):
        r = float(np.mean(residual[idx]))
        s = float(np.mean(dr[idx]))
        if np.any(damage[idx]): out.append("D")
        elif np.any(scar[idx]) and abs(r) < 0.10: out.append("H")
        elif np.any(scar[idx]): out.append("K")
        elif s > 0.045: out.append("R+")
        elif s < -0.045: out.append("R-")
        elif abs(r) < 0.045: out.append("S")
        else: out.append("M")
    return " ".join(out)


def word_distance(a, b):
    a, b = a.split(), b.split()
    m, n = len(a), len(b)
    dp = np.zeros((m+1, n+1), dtype=int)
    dp[:,0] = np.arange(m+1)
    dp[0,:] = np.arange(n+1)
    for i in range(1, m+1):
        for j in range(1, n+1):
            cost = 0 if a[i-1] == b[j-1] else 1
            dp[i,j] = min(dp[i-1,j]+1, dp[i,j-1]+1, dp[i-1,j-1]+cost)
    return int(dp[m,n])


def run_ship(t, y_obs, y_clean, theta_true, damage, scar, name="ship", adaptive=True,
             arp=True, phase_lift=True, memory=True, anti_echo=False,
             harmonic=2.7, amp=0.35, iterations=9, alpha=0.42,
             beta=0.22, mem_gain=0.12, seed=0):
    rng = np.random.default_rng(seed)
    theta = t.copy() + rng.normal(0, 0.0, len(t))
    resistance = np.ones_like(t)
    mem = np.zeros_like(t)
    for _ in range(iterations):
        pred = base(theta, harmonic, amp)
        r = y_obs - pred
        w = robust_weight(r) if anti_echo else np.ones_like(t)
        grad = np.cos(theta) + amp * harmonic * np.cos(harmonic * theta)
        if memory:
            mem = 0.88 * mem + 0.12 * r
        if arp:
            inst = np.abs(np.gradient(r, t))
            inst = inst / (np.percentile(inst, 95) + 1e-9)
            resistance = 1.0 + beta * inst + 0.15 * np.abs(mem)
        if adaptive:
            corr = alpha * w * r * grad / (grad**2 + resistance + 0.08)
            if memory:
                corr += mem_gain * w * mem * grad / (grad**2 + resistance + 0.08)
            theta = theta + corr
        if phase_lift:
            theta = np.unwrap(theta)
    pred = base(theta, harmonic, amp)
    r = y_obs - pred
    rmse_all = float(np.sqrt(np.mean((y_clean - pred)**2)))
    rmse_u = float(np.sqrt(np.mean((y_clean[~damage] - pred[~damage])**2)))
    dmg = float(np.sqrt(np.mean((pred[damage] - y_clean[damage])**2))) if np.any(damage) else 0.0
    if np.any(scar):
        cap = 1.0 - float(np.sqrt(np.mean((y_clean[scar] - pred[scar])**2))) / (float(np.std(y_clean[scar])) + 1e-9)
        cap = float(np.clip(cap, -1, 1))
    else:
        cap = 0.0
    phase_rmse = float(np.sqrt(np.mean((np.unwrap(theta) - np.unwrap(theta_true))**2)))
    score = float(100 - 100*rmse_u - 75*dmg + 35*cap - 8*phase_rmse)
    return dict(name=name, prediction=pred, theta=theta, residual=r, rmse_all=rmse_all,
                rmse_undamaged=rmse_u, damage_echo=dmg, scar_capture=cap,
                phase_rmse=phase_rmse, score=score,
                memory_word=memory_word(t, r, damage, scar, chunks=18))


def fleet_vote(t, y_obs, y_clean, theta_true, damage, scar, harmonic=2.7, amp=0.35,
               fleet_size=28, seed=123):
    rng = np.random.default_rng(seed)
    preds, ths = [], []
    for i in range(fleet_size):
        s = run_ship(t, y_obs, y_clean, theta_true, damage, scar, name=f"fleet_{i}",
                     adaptive=True, arp=True, phase_lift=True, memory=True, anti_echo=True,
                     harmonic=harmonic, amp=amp, iterations=int(rng.integers(7, 12)),
                     alpha=float(rng.uniform(0.25, 0.56)), beta=float(rng.uniform(0.12, 0.35)),
                     mem_gain=float(rng.uniform(0.04, 0.18)), seed=seed+i)
        preds.append(s["prediction"]); ths.append(s["theta"])
    preds, ths = np.array(preds), np.array(ths)
    pred = np.median(preds, axis=0)
    disagree = np.median(np.abs(preds - pred), axis=0)
    th = np.median(np.unwrap(ths, axis=1), axis=0)
    rmse_all = float(np.sqrt(np.mean((y_clean - pred)**2)))
    rmse_u = float(np.sqrt(np.mean((y_clean[~damage] - pred[~damage])**2)))
    dmg = float(np.sqrt(np.mean((pred[damage] - y_clean[damage])**2))) if np.any(damage) else 0.0
    cap = 0.0
    if np.any(scar):
        cap = 1.0 - float(np.sqrt(np.mean((y_clean[scar] - pred[scar])**2))) / (float(np.std(y_clean[scar])) + 1e-9)
        cap = float(np.clip(cap, -1, 1))
    phase_rmse = float(np.sqrt(np.mean((th - np.unwrap(theta_true))**2)))
    score = float(100 - 100*rmse_u - 75*dmg + 35*cap - 8*phase_rmse)
    return dict(name="True Fleet vote: median Phase-Memory EGATL", prediction=pred,
                disagreement=disagree, theta=th, rmse_all=rmse_all, rmse_undamaged=rmse_u,
                damage_echo=dmg, scar_capture=cap, phase_rmse=phase_rmse, score=score,
                memory_word=memory_word(t, y_obs - pred, damage, scar, chunks=18))


def mission_001(outdir, seed=42, fleet_size=28):
    outdir = mkdir(Path(outdir) / "mission_001")
    rng = np.random.default_rng(seed)
    t = np.linspace(0, 6*np.pi, 1400)
    theta = t + 0.32*np.sin(0.37*t) + 0.85/(1 + np.exp(-9*(t - 3.1*np.pi)))
    scar_feature = 0.16*np.exp(-((t - 3.1*np.pi)**2)/(2*0.28**2))*np.sin(8*theta)
    y_clean = base(theta) + scar_feature
    damage = (t > 3.65*np.pi) & (t < 4.05*np.pi)
    scar = (t > 2.85*np.pi) & (t < 3.35*np.pi)
    y_obs = y_clean.copy(); y_obs[damage] += 0.85*rng.normal(size=damage.sum()); y_obs += 0.035*rng.normal(size=len(t))
    ships = [
        run_ship(t,y_obs,y_clean,theta,damage,scar,"Standard observer",False,False,False,False,False,seed=1),
        run_ship(t,y_obs,y_clean,theta,damage,scar,"EGATL body",True,False,False,False,False,seed=2),
        run_ship(t,y_obs,y_clean,theta,damage,scar,"EGATL + ARP",True,True,False,False,False,seed=3),
        run_ship(t,y_obs,y_clean,theta,damage,scar,"EGATL + ARP + Phase-Lift",True,True,True,False,False,seed=4),
        run_ship(t,y_obs,y_clean,theta,damage,scar,"EGATL + ARP + Phase-Lift + Memory",True,True,True,True,False,seed=5),
        run_ship(t,y_obs,y_clean,theta,damage,scar,"Full anti-echo ship",True,True,True,True,True,seed=6),
    ]
    fleet = fleet_vote(t,y_obs,y_clean,theta,damage,scar,fleet_size=fleet_size,seed=seed+1000)
    rows = [{"observer":s["name"],"score":s["score"],"rmse_all":s["rmse_all"],"damage_echo":s["damage_echo"],"scar_capture":s["scar_capture"],"memory_word":s["memory_word"]} for s in ships+[fleet]]
    df = pd.DataFrame(rows).sort_values("score", ascending=False); df.to_csv(outdir/"scores.csv", index=False)
    best = max(ships, key=lambda x:x["score"])
    plt.figure(figsize=(11,5)); plt.plot(t,y_clean,label="true clean"); plt.plot(t,y_obs,label="observed",alpha=.35); plt.plot(t,best["prediction"],label="best ship"); plt.plot(t,fleet["prediction"],label="fleet vote"); plt.axvspan(t[damage][0],t[damage][-1],alpha=.15,label="damage"); plt.legend(); plt.title("Mission 001: Fleet-EGATL recovery"); plt.tight_layout(); plt.savefig(outdir/"recovery.png",dpi=170); plt.close()
    return df


def make_candidate(t, params, seed):
    rng = np.random.default_rng(seed)
    c1,w1,a1,c2,w2,a2,chirp,wind,noise,dmg_amp = params
    theta = t + a1/(1+np.exp(-(t-c1)/w1)) - a2/(1+np.exp(-(t-c2)/w2)) + wind*np.sin(0.21*t + 0.4*np.sin(0.07*t))
    resonance = 0.14*np.exp(-((t-c1)**2)/(2*(3.2*w1)**2))*np.sin((5.5+chirp*t)*theta) - 0.11*np.exp(-((t-c2)**2)/(2*(3.5*w2)**2))*np.cos((4.4+0.5*chirp*t)*theta)
    y_clean = base(theta,2.3,0.28) + resonance
    d_start = c1 + 0.9*(c2-c1)
    damage = (t>d_start) & (t<d_start+0.42*np.pi)
    scar = ((t>c1-.55)&(t<c1+.85)) | ((t>c2-.65)&(t<c2+.95))
    y_obs = y_clean.copy(); y_obs[damage] += dmg_amp*rng.normal(size=damage.sum()); y_obs += noise*rng.normal(size=len(t))
    return theta,y_clean,y_obs,damage,scar


def mission_002(outdir, seed=777, candidates=72, fleet_size=16):
    outdir = mkdir(Path(outdir) / "mission_002")
    rng = np.random.default_rng(seed); t = np.linspace(0, 8*np.pi, 900)
    rows, store = [], []
    for i in range(candidates):
        p = (rng.uniform(1.8*np.pi,3*np.pi),rng.uniform(.035*np.pi,.085*np.pi),rng.uniform(.35,1.15),rng.uniform(4.8*np.pi,6.5*np.pi),rng.uniform(.035*np.pi,.095*np.pi),rng.uniform(.25,1.05),rng.uniform(.005,.032),rng.uniform(.08,.42),rng.uniform(.018,.04),rng.uniform(.35,.85))
        th,yc,yo,dmg,scar = make_candidate(t,p,10000+i)
        std = base(t,2.3,0.28); std_rmse = float(np.sqrt(np.mean((yc-std)**2)))
        fl = fleet_vote(t,yo,yc,th,dmg,scar,2.3,0.28,fleet_size,2000+i)
        gap = std_rmse - fl["rmse_all"]
        score = float(100*gap + 35*fl["scar_capture"] - 70*fl["damage_echo"] - 35*fl["rmse_undamaged"])
        word = memory_word(t, yc-fl["prediction"], dmg, scar, chunks=22)
        rows.append({"candidate":f"Object-{i:03d}","discovery_score":score,"standard_rmse":std_rmse,"fleet_rmse":fl["rmse_all"],"novelty_gap":gap,"scar_capture":fl["scar_capture"],"damage_echo":fl["damage_echo"],"memory_word":word})
        store.append((th,yc,yo,dmg,scar,std,fl,p,word))
    df = pd.DataFrame(rows).sort_values("discovery_score", ascending=False).reset_index(drop=True); df.to_csv(outdir/"candidate_search.csv", index=False)
    bi = int(df.iloc[0]["candidate"].split("-")[1]); th,yc,yo,dmg,scar,std,fl,p,word = store[bi]
    pd.DataFrame({"t":t,"theta_true":th,"y_clean":yc,"y_observed":yo,"standard_prediction":std,"fleet_prediction":fl["prediction"],"fleet_disagreement":fl["disagreement"],"damage_mask":dmg,"scar_mask":scar}).to_csv(outdir/"selected_object_data.csv",index=False)
    (outdir/"selected_summary.json").write_text(json.dumps({"object_name":"Holonomy Scar Lantern","candidate":df.iloc[0]["candidate"],"definition":"A phase-memory object whose hidden identity appears as a stable scar-recovery word under Fleet-EGATL observation.","memory_word":word},indent=2))
    plt.figure(figsize=(11,5)); plt.plot(t,yc,label="true clean"); plt.plot(t,yo,label="observed",alpha=.35); plt.plot(t,std,label="standard"); plt.plot(t,fl["prediction"],label="Fleet-EGATL");
    if np.any(dmg): plt.axvspan(t[dmg][0],t[dmg][-1],alpha=.14,label="damage")
    plt.legend(); plt.title("Mission 002: Holonomy Scar Lantern candidate"); plt.tight_layout(); plt.savefig(outdir/"holonomy_scar_lantern.png",dpi=170); plt.close()
    return df


def norm(p):
    p = p - np.mean(p,axis=0); return p/(np.max(np.linalg.norm(p,axis=1))+1e-9)

def unknot(u): return np.stack([np.cos(u),np.sin(u),np.zeros_like(u)],axis=1)
def trefoil(u): return norm(np.stack([np.sin(u)+2*np.sin(2*u), np.cos(u)-2*np.cos(2*u), -np.sin(3*u)],axis=1))
def fig8(u): return norm(np.stack([(2+np.cos(2*u))*np.cos(3*u),(2+np.cos(2*u))*np.sin(3*u),np.sin(4*u)],axis=1))
def torus(u,p=2,q=5):
    R,r=1.0,.38; return norm(np.stack([(R+r*np.cos(q*u))*np.cos(p*u),(R+r*np.cos(q*u))*np.sin(p*u),r*np.sin(q*u)],axis=1))

def deform(p,u,seed,strength=.07):
    rng=np.random.default_rng(seed); q=p.copy()
    for ax in range(3): q[:,ax]+=strength*rng.uniform(.4,1)*np.sin(int(rng.integers(1,5))*u+rng.uniform(0,2*np.pi))
    return norm(q @ (np.eye(3)+strength*.35*rng.normal(size=(3,3))).T)


def curve_signal(p,u):
    dp=np.gradient(p,u,axis=0); ddp=np.gradient(dp,u,axis=0); speed=np.linalg.norm(dp,axis=1)+1e-9; tan=dp/speed[:,None]
    cross=np.cross(dp,ddp); curv=np.linalg.norm(cross,axis=1)/(speed**3+1e-9)
    tors=np.einsum("ij,ij->i",cross,np.gradient(ddp,u,axis=0))/(np.linalg.norm(cross,axis=1)**2+1e-9)
    phase=np.unwrap(np.arctan2(tan[:,1],tan[:,0])); chord=np.linalg.norm(p-np.roll(p,max(3,len(p)//17),axis=0),axis=1)
    sig=.55*np.tanh(1.2*curv)+.20*np.tanh(.6*tors)+.20*np.sin(phase)+.18*(chord-np.mean(chord)); sig=(sig-np.mean(sig))/(np.std(sig)+1e-9)
    scar=(curv>np.percentile(curv,82)) | (np.abs(tors)>np.percentile(np.abs(tors),85))
    theta = u + (phase-phase[0])/(phase[-1]-phase[0]+1e-9)*(u[-1]-u[0])
    return sig,theta,scar,curv,tors


def knot_fp(p,u,seed=0):
    rng=np.random.default_rng(seed); y,th,scar,curv,tors=curve_signal(p,u); yo=y+.012*rng.normal(size=len(u)); dmg=np.zeros_like(y,dtype=bool)
    fl=fleet_vote(u,yo,y,th,dmg,scar,2.0,.25,14,seed); res=y-fl["prediction"]
    return {"memory_word":memory_word(u,res,dmg,scar,26),"residual_energy":float(np.sqrt(np.mean(res**2))),"curvature_mean":float(np.mean(curv)),"torsion_abs_mean":float(np.mean(np.abs(tors))),"scar_fraction":float(np.mean(scar))}


def mission_003(outdir, seed=303, deformations=6):
    outdir=mkdir(Path(outdir)/"mission_003"); rng=np.random.default_rng(seed); u=np.linspace(0,2*np.pi,900,endpoint=False)
    knots={"unknot":unknot,"trefoil":trefoil,"figure_eight_like":fig8,"torus_2_5":lambda x:torus(x,2,5),"torus_3_4":lambda x:torus(x,3,4)}
    rows=[]
    for name,fn in knots.items():
        p=fn(u); fp0=knot_fp(p,u,seed+len(rows)); rows.append({"knot":name,"variant":"base",**fp0,"distance_to_base":0})
        for d in range(deformations):
            fp=knot_fp(deform(p,u,int(rng.integers(0,1_000_000)),.055+.01*d),u,seed+1000+d)
            rows.append({"knot":name,"variant":f"deform_{d:02d}",**fp,"distance_to_base":word_distance(fp0["memory_word"],fp["memory_word"])})
        fig=plt.figure(figsize=(6,6)); ax=fig.add_subplot(111,projection="3d"); ax.plot(p[:,0],p[:,1],p[:,2]); ax.set_title(name); plt.tight_layout(); plt.savefig(outdir/f"curve_{name}.png",dpi=160); plt.close()
    df=pd.DataFrame(rows); df.to_csv(outdir/"knot_fingerprints.csv",index=False)
    df[df.variant!="base"].groupby("knot").agg(mean_distance=("distance_to_base","mean"),max_distance=("distance_to_base","max"),mean_residual_energy=("residual_energy","mean")).reset_index().to_csv(outdir/"knot_stability.csv",index=False)
    return df


def write_summary(outdir, m1=None, m2=None, m3=None):
    lines=["# Fleet-EGATL Summary","","Toy scaffold summary. Not a proof.",""]
    if m1 is not None:
        top=m1.iloc[0]; lines += ["## Mission 001",f"Top observer: {top['observer']}",f"Score: {top['score']:.3f}",f"Memory word: {top['memory_word']}",""]
    if m2 is not None:
        top=m2.iloc[0]; lines += ["## Mission 002","Object: Holonomy Scar Lantern",f"Candidate: {top['candidate']}",f"Discovery score: {top['discovery_score']:.3f}",f"Memory word: {top['memory_word']}",""]
    if m3 is not None:
        lines += ["## Mission 003","Candidate knot fingerprint test complete.",""]
        for _,r in m3[m3.variant=="base"].iterrows(): lines.append(f"- {r['knot']}: {r['memory_word']}")
    Path(outdir,"summary.md").write_text("\n".join(lines),encoding="utf-8")


def main():
    ap=argparse.ArgumentParser(); ap.add_argument("--mission",choices=["1","2","3","all"],default="all"); ap.add_argument("--outdir",default="fleet_egatl_outputs"); ap.add_argument("--seed",type=int,default=42); ap.add_argument("--fleet-size",type=int,default=28); ap.add_argument("--candidates",type=int,default=72); ap.add_argument("--deformations",type=int,default=6); args=ap.parse_args()
    outdir=mkdir(args.outdir); m1=m2=m3=None
    if args.mission in ["1","all"]:
        print("\nRunning Mission 001..."); m1=mission_001(outdir,args.seed,args.fleet_size); print(m1[["observer","score","memory_word"]].to_string(index=False))
    if args.mission in ["2","all"]:
        print("\nRunning Mission 002..."); m2=mission_002(outdir,args.seed+735,args.candidates,max(12,args.fleet_size//2)); print(m2.head(10)[["candidate","discovery_score","standard_rmse","fleet_rmse","memory_word"]].to_string(index=False))
    if args.mission in ["3","all"]:
        print("\nRunning Mission 003..."); m3=mission_003(outdir,args.seed+303,args.deformations); print(m3[m3.variant=="base"][["knot","memory_word","residual_energy"]].to_string(index=False))
    write_summary(outdir,m1,m2,m3); print(f"\nDone. Outputs written to: {Path(outdir).resolve()}")

if __name__ == "__main__":
    main()
