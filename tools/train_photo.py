"""MNIST + HOG/SVM: higher-resolution model for selected handwritten regions."""
import sys, json, urllib.request
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import cv2, numpy as np, joblib
from sklearn.svm import SVC
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score,precision_recall_fscore_support,confusion_matrix
ROOT=Path(__file__).resolve().parents[1]
def features(im):
 return cv2.HOGDescriptor((28,28),(14,14),(7,7),(7,7),9).compute(im.astype('uint8')).ravel()
def train():
 path=ROOT/'data/mnist.npz'
 if not path.exists():urllib.request.urlretrieve('https://storage.googleapis.com/tensorflow/tf-keras-datasets/mnist.npz',path)
 d=np.load(path); rng=np.random.default_rng(42)
 indices=rng.choice(len(d['y_train']),15000,replace=False)
 X=np.array([features(im) for im in d['x_train'][indices]]); y=d['y_train'][indices]
 a,b,c,e=train_test_split(X,y,test_size=.2,stratify=y,random_state=42)
 best=None; score=-1; search=[]
 for C in [2,8]:
  m=SVC(C=C,probability=True,random_state=42).fit(a,c); v=accuracy_score(e,m.predict(b));search.append({'C':C,'validation_accuracy':v});print('MNIST validation',C,v,flush=True)
  if v>score:score=v;best=m;bestC=C
 best=SVC(C=bestC,probability=True,random_state=42).fit(X,y)
 Xt=np.array([features(im) for im in d['x_test']]); pred=best.predict(Xt);p,r,f,_=precision_recall_fscore_support(d['y_test'],pred,average='macro')
 joblib.dump(best,ROOT/'models/photo.joblib',compress=3)
 metrics={'dataset':'MNIST','train':15000,'validation':3000,'test':10000,'seed':42,'feature':'HOG 28x28 / 324 features','search':search,'C':bestC,'accuracy':accuracy_score(d['y_test'],pred),'precision_macro':p,'recall_macro':r,'f1_macro':f,'confusion_matrix':confusion_matrix(d['y_test'],pred).tolist()}
 (ROOT/'models/photo_metrics.json').write_text(json.dumps(metrics,indent=2));print(metrics['accuracy'],flush=True)
if __name__=='__main__':train()
