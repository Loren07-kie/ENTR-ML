"""Shared normalization used by synthetic-form training and template inference."""
import cv2,numpy as np
def normalize(mask):
 ys,xs=np.where(mask>35)
 if len(xs)<5:return None
 cut=mask[ys.min():ys.max()+1,xs.min():xs.max()+1]
 h,w=cut.shape;scale=20/max(h,w);sw=max(1,round(w*scale));sh=max(1,round(h*scale))
 canvas=np.zeros((28,28),np.uint8);canvas[(28-sh)//2:(28-sh)//2+sh,(28-sw)//2:(28-sw)//2+sw]=cv2.resize(cut,(sw,sh),interpolation=cv2.INTER_AREA)
 moments=cv2.moments(canvas)
 if moments['m00']:
  shift=np.float32([[1,0,13.5-moments['m10']/moments['m00']],[0,1,13.5-moments['m01']/moments['m00']]])
  canvas=cv2.warpAffine(canvas,shift,(28,28))
 return canvas
def features(image):return cv2.HOGDescriptor((28,28),(14,14),(7,7),(7,7),9).compute(image.astype('uint8')).ravel()
