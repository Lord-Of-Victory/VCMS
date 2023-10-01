import hashlib

def generator(course_id,user_id):
    import qrcode

    user_id_data =str(user_id)
    encoded_data=user_id_data.encode()
    hash_obj=hashlib.sha256()
    hash_obj.update(encoded_data)
    user_hash_dig=hash_obj.hexdigest()

    course_id_data =str(course_id)
    encoded_data=course_id_data.encode()
    hash_obj=hashlib.sha256()
    hash_obj.update(encoded_data)
    course_hash_dig=hash_obj.hexdigest()

    qr = qrcode.QRCode(version=4, error_correction=qrcode.constants.ERROR_CORRECT_L, box_size=10, border=3)
    qr_data="/attendance/selfattendance/"+ user_hash_dig +"/"+course_hash_dig
    qr.add_data(qr_data)
    qr.make(fit=True)
    img = qr.make_image()

    # Save the image file
    save_location="static/qr_codes/"+str(user_id)+"_"+str(course_id)+"_qrcode.png"
    img.save(save_location)
    return "qr_codes/"+str(user_id)+"_"+str(course_id)+"_qrcode.png"