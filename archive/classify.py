#!/usr/bin/env python

import getopt, re
import os, os.path, sys, shutil
import flickrapi
import EXIF 

ORIGINAL_TIME = re.compile("^(\d{4})[^\d](\d{2})[^\d](\d{2})\s.+")
POSSIBLE_DUP = re.compile("^(.+)\_[1-9]$")
PHOTO_FORMATS = ['JPEG', 'JPG', 'CR2']
FLICKR_SUPPORTED_FORMATS = ['JPEG', 'JPG']

API_KEY = os.environ['FLICKR_KEY']
API_SECRET = os.environ['FLICKR_SECRET']
ALBUM_ROOT = os.environ['ALBUM_ROOT']
SYNC_ROOT = os.environ['SYNC_ROOT']

def report_status(progress, done):
  if done:
    print ("Done uploading")
  else:      
    print ("At %s%%" % progress)
    
def init_flickr():
  flickr = flickrapi.FlickrAPI(API_KEY, API_SECRET)
  (token, frob) = flickr.get_token_part_one(perms='delete')
  if not token:
    print("Press ENTER after you authorized this program")
  flickr.get_token_part_two((token, frob))
  return flickr

def is_photo_file(photo):
  ext = photo[photo.rindex('.') + 1:] if '.' in photo else ""
  return ext in PHOTO_FORMATS

def is_flickr_supported_file(photo):
  ext = photo[photo.rindex('.') + 1:] if '.' in photo else ""
  return ext in FLICKR_SUPPORTED_FORMATS

def get_photo_original_date(photo):
  f = open(photo, 'rb')
  tags = EXIF.process_file(f, strict=True)
  f.close() 
  original_datetime = tags['EXIF DateTimeOriginal']
  if original_datetime:
    m = ORIGINAL_TIME.match(original_datetime.values)
    if m:
      year = m.group(1)
      month = m.group(2)
      day = m.group(3)
    else:
      raise Exception("Original Datetime %s of photo %s does not match our pattern yyyy:mm:dd" % (original_datetime.values, photo))
  else:
    raise Exception("Photo %s does not have Original Datetime" % photo)
  return year, month, day

def is_same_photo(original, existing):
  return os.path.getsize(original) == os.path.getsize(existing)

def is_bad_file(existing):
  return os.path.getsize(existing) < 1000

def get_sync_file_from(photo):
  sync_path = photo.lstrip(ALBUM_ROOT)
  sync_path = ".".join(sync_path.split('.')[:-1])
  sync_file = os.path.join(SYNC_ROOT, sync_path)
  return sync_file

def is_already_uploaded(photo):
  sync_file = get_sync_file_from(photo)
  return os.path.exists(sync_file)

def update_sync_file(photo):
  sync_file = get_sync_file_from(photo)
  sync_path = os.path.split(sync_file)[0]
  if not os.path.exists(sync_path):
    os.makedirs(sync_path)
  if not os.path.exists(sync_file):
    create_sync_file(sync_file)

def create_sync_file(sync_file):
  try:
    sf = open(sync_file, 'w')
    sf.write("")
    sf.close()
  except Exception as e:
    print ("Failed to create sync file %s" % sync_file)

def get_another_filename(fname):
  i = 1
  while i < 10:
    parts = fname.split('.')
    new_fname = ".".join(parts[:-1]) + "-" + str(i) + "." + parts[-1]
    if not os.path.exists(new_fname):
      return new_fname
    else:
      i += 1
  raise Exception("Cannot create an unique name for %s" % fname) 

def get_classified_file(photo):
  year, month, day = get_photo_original_date(photo)
  classified_file_path = os.path.join(ALBUM_ROOT, year, month, day)
  classified_file = os.path.join(classified_file_path, os.path.basename(photo))

  if os.path.exists(classified_file_path):
    if os.path.exists(classified_file):
      # don't override same file
      print ("Skip duplicate photo %s" % photo)
      return None
  else:
    os.makedirs(classified_file_path)    
  return classified_file

def classify_photo(photo, classified_file, delete_original):
  if delete_original:
    print ("Move %s to %s" % (photo, classified_file))
    shutil.move(photo, classified_file)
  else:
    print ("Copy %s to %s" % (photo, classified_file))
    shutil.copy2(photo, classified_file)
  return classified_file
  
def walk_it(args, work_dir, photo_files):
  
  flickr, classify, upload, tag, delete_original = args
  print ("Start to process %d photos in %s" % (len(photo_files), work_dir))

  for photo_file in photo_files:
    photo = os.path.join(work_dir, photo_file)
    if not os.path.isfile(photo):
      continue

    if not is_photo_file(photo.upper()):
      continue

    try:
      if classify:
        classified_file = get_classified_file(photo)
        if classified_file:
          classify_photo(photo, classified_file, delete_original)
      else:
        classified_file = photo

      if classified_file and upload:
        if not is_flickr_supported_file(classified_file.upper()):
          print ("Skip %s as flickr does not support this format." % classified_file)
        else:
          if is_already_uploaded(classified_file):
            print ("%s is already uploaded" % classified_file)
          else:
            print ("Start uploading %s" % classified_file)
            flickr.upload(filename=classified_file, is_public=0, tags=tag, callback=report_status)
            update_sync_file(classified_file)
    except Exception as e:
      print ("Failed to process photo %s due to %s." % (photo, str(e)))
      raise e

def sync_flickr(flickr):
  for photo in flickr.walk(extras='date_taken', user_id="me"):
    title = photo.get('title')
    date_taken = photo.get('datetaken')
    sync_path = os.path.join(SYNC_ROOT, *date_taken.split(" ")[0].split("-"))
    if not os.path.exists(sync_path):
      os.makedirs(sync_path)
    sync_file = os.path.join(sync_path, title)
    if not os.path.exists(sync_file):
      create_sync_file(sync_file)
    else:
      pass
      
def delete_dups_flickr(flickr, start_year):
  cached = {}
  for photo in flickr.walk(extras='date_taken', user_id="me", sort="date-taken-asc", 
      min_taken_date="%s-01-01" % start_year, max_taken_date="%s-01-01" % (start_year + 1)):
    original_title = photo.get('title').lower()
    photo_id = photo.get('id')
    date_taken = photo.get('datetaken')
    m = POSSIBLE_DUP.match(original_title)
    if m:
      title = m.group(1)
    else:
      title = original_title

    if cached.has_key(title):
      if date_taken in cached[title]:
        print ("Found dup %s (%s) taken at %s" % (original_title, photo_id, date_taken))
        flickr.photos_delete(photo_id=photo_id)
      else:
        cached[title].append(date_taken)
        # print "Append new entry for %s - %s taken at different time %s - %s" % (original_title, title, cached[title], date_taken)
    else:
      cached[title] = [date_taken]

if __name__ == '__main__':

  upload = False
  sync = False
  classify = False
  remove_original = False
  deletedup = False
  tag = None
  upload_root = os.environ['UPLOAD_ROOT']

  try:
    options, remainder = getopt.gnu_getopt(sys.argv[1:], 'd:t:cursx:',
                                               ['sourcedir=',
                                                'tag=',
                                                'classify',
                                                'upload',
                                                'removeoriginal',
                                                'sync',
                                                'deletedup'
                                                ])
    for opt, arg in options :       
      if opt in ('-d', '--sourcedir'):
        upload_root = arg
      elif opt in ('-t', '--tag'):
        tag = arg
      elif opt in ('-r', '--removeoriginal'):
        remove_original = True
      elif opt in ('-c', '--classify'):
        classify = True
      elif opt in ('-u', '--upload'):
        upload = True
      elif opt in ('-s', '--sync'):
        sync = True
      elif opt in ('-x', '--deletedup'):
        deletedup = True
        start_year = int(arg)

  except getopt.GetoptError as e:
    sys.exit(2)

  if sync:
    sync_flickr(init_flickr())
  elif deletedup:
    delete_dups_flickr(init_flickr(), start_year)
  else:
    if (not classify) and (not upload):
      print ("No operation specified")
      sys.exit(2)

    args = (init_flickr(), classify, upload, tag, remove_original)
    os.path.walk(upload_root, walk_it, args)
