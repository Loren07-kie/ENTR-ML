"""Reproducible academic benchmark. No test samples used for tuning."""
import os, sys, json, time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import numpy as np
from sklearn.datasets import load_digits
from sklearn.model_selection import train_test_split, GridSearchCV, StratifiedKFold
from sklearn.neural_network import MLPClassifier
from sklearn.neighbors import KNeighborsClassifier
from sklearn.svm import SVC
from sklearn.metrics import accuracy_score, precision_recall_fscore_support, confusion_matrix, classification_report
from sklearn.cluster import KMeans
from sklearn.linear_model import LinearRegression
import joblib

def train():
 root=Path(__file__).resolve().parents[1]; (root/'models').mkdir(exist_ok=True)
 d=load_digits(); X=d.data/16.; y=d.target
 a,b,c,e=train_test_split(X,y,test_size=.2,stratify=y,random_state=42)
 cv=StratifiedKFold(3,shuffle=True,random_state=42)
 specs={'KNN':(KNeighborsClassifier(),{'n_neighbors':[3,5]}),'SVM':(SVC(probability=True,random_state=42),{'C':[1,10],'gamma':['scale']}),'MLP':(MLPClassifier(hidden_layer_sizes=(64,32),activation='relu',solver='adam',max_iter=180,random_state=42),{'alpha':[.0001,.001]})}
 results={}; best=None; best_cv=-1
 for name,(model,grid) in specs.items():
  t=time.time(); search=GridSearchCV(model,grid,cv=cv,scoring='f1_macro',n_jobs=1).fit(a,c)
  pred=search.predict(b); p,r,f,_=precision_recall_fscore_support(e,pred,average='macro',zero_division=0)
  results[name]={'accuracy':accuracy_score(e,pred),'precision_macro':p,'recall_macro':r,'f1_macro':f,'cv_f1':search.best_score_,'params':search.best_params_,'seconds':round(time.time()-t,2),'confusion_matrix':confusion_matrix(e,pred).tolist(),'report':classification_report(e,pred,output_dict=True,zero_division=0)}
  if search.best_score_>best_cv: best=search.best_estimator_; best_cv=search.best_score_; selected=name
  print(name,results[name]['accuracy'],flush=True)
 joblib.dump(best,root/'models/digits.joblib')
 rng=np.random.default_rng(42); fields=rng.integers(2,30,120); quality=rng.uniform(.35,1,120); seconds=2+fields*.45+(1-quality)*4+rng.normal(0,.3,120)
 reg=LinearRegression().fit(np.c_[fields,quality],seconds)
 cluster=KMeans(n_clusters=3,random_state=42,n_init=10).fit(a)
 out={'dataset':'UCI Optical Recognition of Handwritten Digits / sklearn load_digits','samples':len(y),'train':len(c),'test':len(e),'seed':42,'selected':selected,'selection_rule':'Highest mean validation macro F1, without test selection','models':results,'synthetic_regression':{'coefficients':reg.coef_.tolist(),'intercept':reg.intercept_,'r2_training':reg.score(np.c_[fields,quality],seconds)},'kmeans':{'inertia':cluster.inertia_,'clusters':3},'test_truth':e[:30].tolist(),'test_predictions':best.predict(b[:30]).tolist()}
 (root/'models/metrics.json').write_text(json.dumps(out,indent=2),encoding='utf-8')
 np.savez_compressed(root/'data/benchmark_samples.npz',images=b[:30].reshape(-1,8,8),truth=e[:30],prediction=best.predict(b[:30]))
 return out
if __name__=='__main__': train()
