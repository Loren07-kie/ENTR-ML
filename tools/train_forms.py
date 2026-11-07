"""Actually train and evaluate a form-digit model; never train on demo/test answers."""
from pathlib import Path
import sys,json,time
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import cv2,numpy as np,joblib
from sklearn.svm import SVC
from sklearn.model_selection import GridSearchCV,StratifiedKFold
from sklearn.metrics import accuracy_score,precision_recall_fscore_support,confusion_matrix
from digit_features import normalize,features
ROOT=Path(__file__).resolve().parents[1]
def transformed(image):
 value=normalize(image)
 return features(value if value is not None else np.zeros((28,28),np.uint8))
def train():
 started=time.time();d=np.load(ROOT/'data/mnist.npz');rng=np.random.default_rng(427)
 base_used=np.random.default_rng(42).choice(len(d['y_train']),15000,replace=False)
 remaining=np.setdiff1d(np.arange(len(d['y_train'])),base_used)
 train_ids=rng.choice(base_used,6000,replace=False);val_ids=rng.choice(remaining,1500,replace=False)
 X=np.array([transformed(i) for i in d['x_train'][train_ids]]);y=d['y_train'][train_ids]
 aug=[];aug_y=[]
 for index in rng.choice(train_ids,1000,replace=False):
  angle=float(rng.uniform(-10,10));scale=float(rng.uniform(.85,1.1));matrix=cv2.getRotationMatrix2D((13.5,13.5),angle,scale)
  image=cv2.warpAffine(d['x_train'][index],matrix,(28,28));aug.append(transformed(image));aug_y.append(int(d['y_train'][index]))
 X=np.r_[X,np.array(aug)];y=np.r_[y,np.array(aug_y)]
 validation=np.array([transformed(i) for i in d['x_train'][val_ids]]);truth=d['y_train'][val_ids]
 cv=StratifiedKFold(3,shuffle=True,random_state=427)
 search=GridSearchCV(SVC(probability=True,random_state=427),{'C':[1,4]},cv=cv,scoring='f1_macro',n_jobs=1).fit(X,y)
 base=joblib.load(ROOT/'models/photo.joblib');models={'base_svm':base,'adapted_svm':search.best_estimator_};validation_scores={}
 for name,model in models.items():validation_scores[name]=float(precision_recall_fscore_support(truth,model.predict(validation),average='macro',zero_division=0)[2])
 selected=max(validation_scores,key=validation_scores.get);model=models[selected]
 test_ids=rng.choice(len(d['y_test']),2000,replace=False);test=np.array([transformed(i) for i in d['x_test'][test_ids]]);real=d['y_test'][test_ids];prediction=model.predict(test)
 p,r,f,_=precision_recall_fscore_support(real,prediction,average='macro',zero_division=0)
 result={'seed':427,'source':'MNIST official training/test, with separate demo forms','train':len(y),'augmented_train':len(aug),'validation':len(truth),'test':len(real),'cv_folds':3,'cv_f1':search.best_score_,'best_params':search.best_params_,'validation_f1':validation_scores,'selected':selected,'accuracy':accuracy_score(real,prediction),'precision_macro':p,'recall_macro':r,'f1_macro':f,'confusion_matrix':confusion_matrix(real,prediction).tolist(),'seconds':round(time.time()-started,2),'scope':'isolated digits normalized as form cells; not universal form/text accuracy','leakage_control':'validation indices excluded from original base-model training; official test never used for fitting or selection'}
 joblib.dump(search.best_estimator_,ROOT/'models/forms_candidate.joblib',compress=3)
 joblib.dump(model,ROOT/'models/forms_digits.joblib',compress=3);(ROOT/'models/forms_training_metrics.json').write_text(json.dumps(result,indent=2),encoding='utf-8');print(json.dumps({k:v for k,v in result.items() if k!='confusion_matrix'},indent=2),flush=True)
 from model_io import split_model
 split_model(ROOT/'models/forms_candidate.joblib');split_model(ROOT/'models/forms_digits.joblib')
 return result
if __name__=='__main__':train()
