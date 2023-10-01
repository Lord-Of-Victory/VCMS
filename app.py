#------------------------------------------------ Imports -------------------------------------------------------------------#

from flask import Flask, request, render_template,redirect, session,url_for,flash
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from werkzeug.utils import secure_filename
import hashlib
from qr_generator import qr_gen
import os

app = Flask(__name__)
app.secret_key = 'SuperSecretKey'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///VirtualClassroom.sqlite3'
db=SQLAlchemy()
db.init_app(app)
app.app_context().push()


#------------------------------------------------- Database Models -----------------------------------------------------------#

class Users(db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(80), nullable=False)
    roles = db.Column(db.String(50), nullable=False)
    is_admin = db.Column(db.Boolean, default=False)

class Course(db.Model):
    __tablename__ = 'courses'
    id = db.Column(db.Integer, primary_key=True,unique=True)
    name = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text)
    start_date = db.Column(db.Date)
    end_date = db.Column(db.Date)
    created_at = db.Column(db.TIMESTAMP, nullable=False, server_default=db.func.current_timestamp())
    updated_at = db.Column(db.TIMESTAMP, nullable=False, server_default=db.func.current_timestamp(), onupdate=db.func.current_timestamp())
    topics = db.relationship('Topic', backref='course', lazy=True,primaryjoin="Course.id == Topic.course_id")

class CourseEnrollment(db.Model):
    __tablename__ = 'course_enrollments'
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), primary_key=True)
    course_id = db.Column(db.Integer, db.ForeignKey('courses.id'), primary_key=True)
    user_qr = db.Column(db.String(255), unique=True, nullable=False)
    user = db.relationship('Users', backref=db.backref('enrollment'),primaryjoin="CourseEnrollment.user_id == Users.id" )
    course = db.relationship('Course', backref=db.backref('enrollment'), primaryjoin="CourseEnrollment.course_id == Course.id")

class CourseInstructor(db.Model):
    __tablename__ = 'course_instructors'
    course_id = db.Column(db.Integer, db.ForeignKey('courses.id'), primary_key=True)
    instructor_id = db.Column(db.Integer, db.ForeignKey('users.id'), primary_key=True)
    instructor = db.relationship('Users', backref=db.backref('courses_taught', lazy=True))
    course = db.relationship('Course', backref=db.backref('instructors', lazy=True))

    __table_args__ = (
        db.Index('instructor_id_idx', instructor_id),
        db.ForeignKeyConstraint(['course_id'], ['courses.id'], ondelete='CASCADE', onupdate='CASCADE', name='course_id_fk'),
        db.ForeignKeyConstraint(['instructor_id'], ['users.id'], ondelete='CASCADE', onupdate='CASCADE', name='instructor_id_fk'),
    )

class Attendance(db.Model):
    __tablename__ = 'attendance'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    course_id = db.Column(db.Integer, db.ForeignKey('courses.id'), nullable=False)
    attendance_date = db.Column(db.Date, nullable=False)
    status = db.Column(db.Enum('present', 'absent'), nullable=False, default='absent')

    user = db.relationship('Users', backref=db.backref('attendance', lazy=True))
    course = db.relationship('Course', backref=db.backref('attendance', lazy=True))

    __table_args__ = (
        db.UniqueConstraint('user_id', 'course_id', 'attendance_date', name='unique_attendance'),)

class Topic(db.Model):
    __tablename__ = "topics"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50))
    description=db.Column(db.Text)
    course_id = db.Column(db.Integer, db.ForeignKey('courses.id'))
    messages = db.relationship('Message', backref='topic', lazy=True,primaryjoin="Topic.id == Message.topic_id")
    uploads=db.relationship('Upload', backref='topic', lazy=True,primaryjoin="Topic.id == Upload.topic_id")

class Assignment(db.Model):
    __tablename__ = 'assignments'
    id = db.Column(db.Integer, primary_key=True)
    course_id = db.Column(db.Integer, db.ForeignKey('courses.id'), nullable=False)
    title = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text)
    due_date = db.Column(db.Date)
    created_at = db.Column(db.DateTime, default=datetime.now)
    updated_at = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)
    course = db.relationship('Course', backref=db.backref('assignments', lazy=True),primaryjoin="Assignment.course_id == Course.id")

    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    user = db.relationship('Users', backref=db.backref('assignments', lazy=True),primaryjoin="Assignment.user_id == Users.id")

    def __repr__(self):
        return f"<Assignment {self.id} - {self.title}>"
    

class Message(db.Model):
    __tablename__ = "messages"
    id = db.Column(db.Integer, primary_key=True)
    text = db.Column(db.Text)
    topic_id = db.Column(db.Integer, db.ForeignKey('topics.id'))
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    creator = db.relationship('Users', backref='messages',lazy=True,primaryjoin="Message.created_by == Users.id")

class Upload(db.Model):
    __tablename__ = "uploads"
    id = db.Column(db.Integer, primary_key=True)
    topic_id = db.Column(db.Integer, db.ForeignKey('topics.id', ondelete='CASCADE', onupdate='CASCADE'), nullable=False)
    link_to_file = db.Column(db.String(255), unique=True, nullable=False)

    def __repr__(self):
        return f'<Upload {self.id}>'

#-----------------------------------------------------------Functions------------------------------------

def create_admin():
    db.create_all()
    if Users.query.filter_by(username="admin").first():
        return
    admin=Users(id=1,username="admin",password = "admin",email="admin@admin.admin",is_admin=True,roles="teacher")
    db.session.add(admin)
    db.session.commit()
    return

def delete_course(course_id):
    course=Course.query.get(course_id)
    course_enrollments=CourseEnrollment.query.filter_by(course_id=course_id).all()
    course_instructors=CourseInstructor.query.filter_by(course_id=course_id).all()
    attendances=Attendance.query.filter_by(course_id=course_id).all()
    assignments=Assignment.query.filter_by(course_id=course_id).all()
    topics=Topic.query.filter_by(course_id=course_id).all()


    flash('Deleted Course'+ str((course.id,course.name)))
    for course_enrollment in course_enrollments:
        db.session.delete(course_enrollment)
    for course_instructor in course_instructors:
        db.session.delete(course_instructor)
    for assignment in assignments:
        db.session.delete(assignment)
    for topic in topics:
        uploads=Upload.query.filter_by(topic_id=topic.id).all()
        messages=Message.query.filter_by(topic_id=topic.id).all()
        for upload in uploads:
            db.session.delete(upload)
        for message in messages:
            db.session.delete(message)
        db.session.delete(topic)
    db.session.delete(course)
    return


#<--------------------------------------------------- Routes ------------------------------------------------------------>#

@app.route('/',methods=['GET','POST'])
def homepage():
    return render_template('homepage.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'GET':
        return render_template('register.html')
    elif request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']
        confirm_password = request.form['confirm_password']
        roles = request.form['role']
        
        errors = []
        if not username:
            errors.append('Username is required')
        if not email:
            errors.append('Email is required')
        if not password:
            errors.append('Password is required')
        if password != confirm_password:
            errors.append('Passwords do not match')
        if Users.query.filter_by(username=username).first():
            errors.append('Username is already taken')
        if Users.query.filter_by(email=email).first():
            errors.append('Email already exists')
        
        if errors:
            return render_template('register.html', errors=errors)
        else:

            user = Users(username=username, email=email, password=password,roles=roles)
            db.session.add(user)
            db.session.commit()

            session['registered'] = True
            session['user_id'] = user.id
            session['user_role'] = user.roles
            session['user_email'] = user.email
            session['username'] = user.username
            session['is_admin'] = user.is_admin
            flash('Sign Up Successful')
            return redirect('/dashboard')
        
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'GET':
        return render_template('login.html')
    elif request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        user = Users.query.filter_by(username=username).first()
        if user and user.password == password:
            session['user_id'] = user.id
            session['user_role'] = user.roles
            session['user_email'] = user.email
            session['username'] = user.username
            session['is_admin'] = user.is_admin
            flash("Successfully Logged In")
            return redirect(url_for('dashboard'))
        else:
            error = 'Invalid username or password'
            return render_template('login.html', error=error)

@app.route('/admin_panel')
def admin_panel():
    if 'user_id' not in session or session['user_id']==None:
        flash("Login to continue")
        return redirect('/login')
    if not session['is_admin']:
        session.clear()
        flash('Authorization Required')
        return redirect(url_for('login'))
    else:
        users=Users.query.all()
        courses=Course.query.all()
        return render_template('admin_panel.html',users=users,courses=courses)
    
@app.route('/admin_panel/delete')
def delete():
    if 'user_id' not in session or session['user_id']==None:
        flash("Login to continue")
        return redirect('/login')
    if not session['is_admin']:
        session.clear()
        flash('Authorization Required')
        return redirect(url_for('login'))
    else:
        course_id=request.args.get('course_id')
        user_id=request.args.get('user_id')
        uploads_id=request.args.get('upload_id')
        assignment_id=request.args.get('assignment_id')
        topic_id=request.args.get('topic_id')
        message_id=request.args.get('message_id')
   
        if course_id:
            delete_course(course_id)
            db.session.commit()

        if user_id:
            user=Users.query.get(user_id)
            course_enrollments=CourseEnrollment.query.filter_by(user_id=user_id).all()
            course_instructors=CourseInstructor.query.filter_by(instructor_id=user_id).all()
            assignments=Assignment.query.filter_by(user_id=user_id).all()
            attendances=Attendance.query.filter_by(user_id=user_id).all()
            messages=Message.query.filter_by(created_by=user_id).all()

            flash('Deleted User '+ str((user.id,user.username)))

            for course_enrollment in course_enrollments:
                db.session.delete(course_enrollment)
            for course_instructor in course_instructors:
                delete_course(course_instructor.course_id)
                db.session.delete(course_instructor)
            for attendance in attendances:
                db.session.delete(attendance)
            for assignment in assignments:
                db.session.delete(assignment)
            for message in messages:
                db.session.delete(message)
            
            flash('Deleted All Corresponding data of : '+ str((user.id,user.username)))
            db.session.delete(user)
            db.session.commit()
        if uploads_id:
            upload=Upload.query.get(uploads_id)
            topic_id=upload.topic_id
            course_id=upload.topic.course_id
            file_path = 'static/'+upload.link_to_file
            if os.path.exists(file_path):
                os.remove(file_path)
                print(f"{file_path} deleted successfully")
            else:
                print(f"{file_path} does not exist")
            flash('Deleted Upload id :'+ str((upload.id)))
            db.session.delete(upload)
            db.session.commit()
            return redirect(url_for('view_topic',topic_id=topic_id,course_id=course_id))
        if assignment_id:
            assignment=Assignment.query.get(assignment_id)
            flash('Deleted Assignment '+ str((assignment.id,assignment.title)))
            db.session.delete(assignment)
            db.session.commit()
            return redirect(url_for('dashboard'))
        if topic_id:
            topic=Topic.query.get(topic_id)
            course_id=topic.course_id
            uploads=Upload.query.filter_by(topic_id=topic_id).all()
            messages=Message.query.filter_by(topic_id=topic_id).all()
            
            flash('Deleted Topic '+ str(topic.name))
            for upload in uploads:
                db.session.delete(upload)
            for message in messages:
                db.session.delete(message)
            db.session.delete(topic)
            db.session.commit()
            return redirect(url_for('view_course',course_id=course_id))
        if message_id:
            message=Message.query.get(message_id)
            flash('Deleted Message '+ str(message.id))
            db.session.delete(message)
            db.session.commit()
        return redirect(url_for('admin_panel'))



@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session or session['user_id']==None:
        return redirect('/login')
    
    user = Users.query.get(session['user_id'])
    enrollments = CourseEnrollment.query.filter_by(user_id=session['user_id']).all()
    courses = [enrollment.course for enrollment in enrollments]
    
    return render_template('dashboard.html', user=user,courses=courses)

@app.route('/courses')
def courses():
    if 'user_id' not in session or session['user_id']==None:
        return redirect('/login')
    
    courses = Course.query.all()
    user = Users.query.get(session['user_id'])
    course_enrolled=CourseEnrollment.query.filter_by(user_id=session['user_id']).all()
    enrolled=[]
    for i in course_enrolled:
        enrolled.append(i.course_id)
    return render_template('courses.html', courses=courses,user=user,course_enrolled=enrolled)

@app.route('/admin_panel/courses')
def admin_panel_courses():
    if 'user_id' not in session or session['user_id']==None:
        return redirect('/login')
    if not session['is_admin']:
        session.clear()
        flash('Authorization Required')
        return redirect(url_for('login'))
    else:
        courses = Course.query.all()
        return render_template('admin_panel_courses.html',courses=courses)

@app.route('/admin_panel/users')
def admin_panel_users():
    if 'user_id' not in session or session['user_id']==None:
        return redirect('/login')
    if not session['is_admin']:
        session.clear()
        flash('Authorization Required')
        return redirect(url_for('login'))
    else:
        users = Users.query.all()
        return render_template('admin_panel_users.html',users=users,role='Users')

@app.route('/admin_panel/students')
def admin_panel_students():
    if 'user_id' not in session or session['user_id']==None:
        return redirect('/login')
    if not session['is_admin']:
        session.clear()
        flash('Authorization Required')
        return redirect(url_for('login'))
    else:
        users = Users.query.filter_by(roles='student')
        return render_template('admin_panel_users.html',users=users,role='Students')

@app.route('/admin_panel/students/courses')
def admin_panel_students_courses():
    user_id=request.args.get('user_id')
    course_enrolled=CourseEnrollment.query.filter_by(user_id=user_id).all()
    enrolled=[]
    for course_enroll in course_enrolled:
        enrolled.append(course_enroll.course)
    return render_template('admin_panel_students_course.html',courses=enrolled)

@app.route('/admin_panel/students/courses_inst')
def admin_panel_students_courses_inst():
    user_id=request.args.get('user_id')
    course_inst=CourseInstructor.query.filter_by(instructor_id=user_id).all()
    inst=[]
    for course_inst_obj in course_inst:
        inst.append(course_inst_obj.course)
    return render_template('admin_panel_students_course.html',courses=inst)

@app.route('/admin_panel/teachers')
def admin_panel_teachers():
    if 'user_id' not in session or session['user_id']==None:
        return redirect('/login')
    if not session['is_admin']:
        session.clear()
        flash('Authorization Required')
        return redirect(url_for('login'))
    else:
        users = Users.query.filter_by(roles='teacher')
        return render_template('admin_panel_users.html',users=users,role='Teachers')

@app.route('/admin_panel/users_registration')
def admin_panel_user_registration():
    if 'user_id' not in session or session['user_id']==None:
        return redirect('/login')
    if not session['is_admin']:
        session.clear()
        flash('Authorization Required')
        return redirect(url_for('login'))
    else:
        return render_template('admin_panel_user_registration.html')

@app.route('/admin_panel/user_edit', methods=['GET','POST'])
def admin_panel_user_edit():
    if 'user_id' not in session or session['user_id']==None:
        return redirect('/login')
    if not session['is_admin']:
        session.clear()
        flash('Authorization Required')
        return redirect(url_for('login'))
    else:
        if request.method=='POST':
            user_id=request.form['user_id']
            user=Users.query.get(user_id)
            username=request.form['username']
            email=request.form['email']
            password=request.form['password']
            role=request.form['role']
            if username:
                user.username=username
            if email:
                user.email=email
            if password:
                user.password=password
            if role:
                user.roles=role
            db.session.commit()
            return redirect(url_for('admin_panel'))
        
        user_id=request.args.get('user_id')
        # print(user_id)
        user=Users.query.get(user_id)
        return render_template('admin_panel_user_edit.html',user=user)
        

@app.route('/admin_user_register', methods=['GET','POST'])
def admin_user_register():
    if 'user_id' not in session or session['user_id']==None:
        return redirect('/login')
    if not session['is_admin']:
        session.clear()
        flash('Authorization Required')
        return redirect(url_for('login'))
    
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']
        confirm_password = request.form['confirm_password']
        roles = request.form['role']
        
        errors = []
        if not username:
            errors.append('Username is required')
            flash('Username is required')
        if not email:
            errors.append('Email is required')
            flash('Email is required')
        if not password:
            errors.append('Password is required')
            flash('Password is required')
        if password != confirm_password:
            errors.append('Passwords do not match')
            flash('Passwords do not match')
        if Users.query.filter_by(username=username).first():
            errors.append('Username is already taken')
            flash('Username is already taken')
        if Users.query.filter_by(email=email).first():
            errors.append('Email already exists')
            flash('Email already exists')
        
        if errors:
            return redirect(url_for('admin_panel'))
        else:
            user = Users(username=username, email=email, password=password,roles=roles)
            db.session.add(user)
            db.session.commit()
            flash('User Registered' + "("+str(user.id)+ " " +str(user.username)+")")
            return redirect('admin_panel')
        
@app.route('/user_to_admin', methods=['GET','POST'])
def user_to_admin():
    if 'user_id' not in session or session['user_id']==None:
        return redirect('/login')
    if not session['is_admin']:
        session.clear()
        flash('Authorization Required')
        return redirect(url_for('login'))
    else:
        user_id=request.args.get('user_id')
        user=Users.query.get(user_id)
        user.is_admin=True
        db.session.commit()
        flash('User Promoted')
        return redirect('admin_panel')

@app.route('/courses/new', methods=['GET', 'POST'])
def new_course():
    if 'user_id' not in session or session['user_id']==None:
        return redirect('/login')
    
    user = Users.query.get(session['user_id'])
    if request.method == 'POST':
        name = request.form['course_title']
        description = request.form['course_desc']
        start_date = datetime.strptime(request.form['start_date'], '%Y-%m-%d').date()
        end_date = datetime.strptime(request.form['end_date'], '%Y-%m-%d').date()
        
        course = Course(name=name, description=description, start_date=start_date, end_date=end_date)
        db.session.add(course)
        db.session.commit()
        course_instructor=CourseInstructor(course_id=course.id,instructor_id=user.id)
        qr_location=qr_gen.generator(course_id=course.id,user_id=user.id)
        course_enrollment=CourseEnrollment(course_id=course.id,user_id=user.id,user_qr=qr_location)
        db.session.add(course_instructor)
        db.session.add(course_enrollment)
        db.session.commit()
        return redirect(url_for('courses'))
    else:
        return render_template('new_course.html',user=user)
    

@app.route('/courses/<int:course_id>/topics/new', methods=['GET', 'POST'])
def new_topic(course_id):
    if 'user_id' not in session or session['user_id']==None:
        return redirect('/login')
    
    if request.method == 'POST':
        name = request.form['title']
        description = request.form['description']
        topic = Topic(name=name, course_id=course_id,description=description)
        db.session.add(topic)
        db.session.commit()
        return redirect(url_for('view_course', course_id=course_id))
    else:
        return render_template('new_topic.html', course_id=course_id)

@app.route('/courses/<int:course_id>/topics/<int:topic_id>')
def view_topic(course_id, topic_id):
    if 'user_id' not in session or session['user_id']==None:
        return redirect('/login')
    
    topic = Topic.query.get(topic_id)
    return render_template('view_topic.html', course_id=course_id, topic=topic)

@app.route('/courses/<int:course_id>/topics/<int:topic_id>/messages/new', methods=['GET', 'POST'])
def new_message(course_id, topic_id):
    if 'user_id' not in session or session['user_id']==None:
        return redirect('/login')
    
    if request.method == 'POST':
        text = request.form['msg_text']
        created_by = session['user_id']
        message = Message(text=text, topic_id=topic_id,created_by=created_by)
        db.session.add(message)
        db.session.commit()
        return redirect(url_for('view_topic', course_id=course_id, topic_id=topic_id))
    else:
        return render_template('new_message.html', course_id=course_id, topic_id=topic_id)

@app.route('/courses/<int:course_id>')
def view_course(course_id):
    if 'user_id' not in session or session['user_id']==None:
        return redirect('/login')
    
    user=Users.query.get(session['user_id'])
    course = Course.query.get(course_id)
    course_enrollment = CourseEnrollment.query.filter_by(course_id=course.id,user_id=user.id).first()
    return render_template('view_course.html', course=course,user=user,course_enrollment=course_enrollment)

@app.route('/courses/<int:course_id>/assignment/<int:assignment_id>')
def view_assignment(course_id,assignment_id):
    if 'user_id' not in session or session['user_id']==None:
        return redirect('/login')
    
    course = Course.query.get_or_404(course_id)
    assignments = Assignment.query.get(assignment_id)
    return render_template('assignments.html', course=course, assignments=assignments)

@app.route('/courses/<int:course_id>/assignments/new' , methods=['GET', 'POST'])
def new_assignments(course_id):
    if 'user_id' not in session or session['user_id']==None :
        return redirect('/login')
    if session['user_role']!='teacher':
        return redirect(url_for('assignments',course_id=course_id))
    
    if request.method == 'POST':
        name = request.form['assignment_title']
        desc = request.form['assignment_desc']
        due = request.form['end_date']
        user_id = session['user_id']
        assignment = Assignment(title=name,description = desc,due_date = due,course_id=course_id,user_id=user_id)
        db.session.add(assignment)
        db.session.commit()
        return redirect(url_for('view_course', course_id=course_id))
    else:
        return render_template('new_assignments.html', course_id=course_id)

@app.route('/courses/<int:course_id>/enroll')
def enroll_in_course(course_id):
    if 'user_id' not in session or session['user_id']==None:
        return redirect('/login')
    
    course = Course.query.get_or_404(course_id)
    user = Users.query.get(session['user_id'])

    duplicate_check = CourseEnrollment.query.filter_by(course_id=course.id, user_id=user.id).first()
    if duplicate_check:
        flash('Already enrolled')
        return redirect(url_for('dashboard'))
    else:
        qr_location=qr_gen.generator(course_id=course.id,user_id=user.id)
        course_enrol=CourseEnrollment(course_id=course.id,user_id=user.id,user_qr=qr_location)
        db.session.add(course_enrol)
        db.session.commit()
        return redirect(url_for('dashboard'))
    
@app.route('/courses/<int:course_id>/unenroll')
def unenroll(course_id):
    if 'user_id' not in session or session['user_id']==None:
        return redirect('/login')
    
    course_unenroll=CourseEnrollment.query.filter_by(course_id=course_id, user_id=session['user_id']).first()
    db.session.delete(course_unenroll)
    db.session.commit()
    flash("Unenrolled Successfully")
    return redirect(url_for('dashboard'))
    

@app.route('/attendance/selfattendance/<user_id>/<course_id>', methods=['GET'])
def scan_attendance(course_id,user_id):
    if 'user_id' not in session or session['user_id']==None:
        return redirect('/login')
    
    course_enrollments=CourseEnrollment.query.filter_by(user_id=session['user_id']).all()
    course_hashes=[]
    for course_enrollment in course_enrollments:
        encoded_data=str(course_enrollment.course_id).encode()
        hash_obj=hashlib.sha256()
        hash_obj.update(encoded_data)
        course_id_hash_dig=hash_obj.hexdigest()
        course_hashes.append((course_enrollment.course_id,course_id_hash_dig))

    #print (course_hashes)
        
    user_id_data = session['user_id']
    encoded_data=str(user_id_data).encode()
    hash_obj=hashlib.sha256()
    hash_obj.update(encoded_data)
    user_id_hash_dig=hash_obj.hexdigest()
   #print(user_id)

    for hash in course_hashes:
        if hash[1] == course_id:
            course__id=hash[0]
            if user_id==user_id_hash_dig:
                dup_check=Attendance.query.filter_by(user_id=user_id_data, course_id=course__id, attendance_date=datetime.now().date(), status='present').first()
                #print(dup_check)
                if dup_check:
                    flash("Already Marked Attendance For Today")
                    return redirect(url_for('dashboard'))
                    
                attendance = Attendance(user_id=user_id_data, course_id=course__id, attendance_date=datetime.now().date(), status='present')
                db.session.add(attendance)
                db.session.commit()
                flash('Attendance Marked')
                return redirect(url_for('dashboard'))
    flash('Technical Error')
    return redirect(url_for('dashboard'))

@app.route('/attendance/<int:course_id>', methods=['GET'])
def attendance_stats(course_id):
    if 'user_id' not in session or session['user_id']==None:
        return redirect('/login')
    
    course_instructor=CourseInstructor.query.filter_by(course_id=course_id).first()

    if  session['is_admin']==False:
        if (session['user_id'] != course_instructor.instructor_id):
            session.clear()
            flash("Course Creator's Login Required")
            return redirect(url_for('login'))
    
    course_enroll=CourseEnrollment.query.filter_by(course_id=course_id).all()
    attend_dict={}
    for record in course_enroll:
        attend_dict[record.user_id]=[0,record.user.username]
    attendance=Attendance.query.filter_by(course_id=course_id).all()
    for record in attendance:
        attend_dict[record.user_id][0]+=1
    #print(attend_dict)
        
    return render_template("attendance_stats.html",attendance=attendance,attend_dict=attend_dict)
    


#------------------------------- Unused Code Start -------------------------------------------#
@app.route('/attendance/<int:course_id>', methods=['GET', 'POST'])
def mark_attendance(course_id):
    if 'user_id' not in session or session['user_id']==None:
        return redirect('/login')
    
    course_instructor=CourseInstructor.query.get(course_id)
    if session['user_id'] == course_instructor.user_id:
        return redirect(url_for('login',error="Only Teachers can visit this page"))
    
    course = Course.query.get_or_404(course_id)
    course_enrollments = CourseEnrollment.query.filter_by(course_id=course_id).all()
    user_ids=[]
    for course_enrollment in course_enrollments:
        user_ids.append(course_enrollment.user_id)
    users=[]
    for user_id in user_ids:
        user=Users.query.get(user_id)
        users.append(user)
    attendance_date = datetime.now().date()

    if request.method == 'POST':
        for user in users:
            status = request.form.get(str(user.id))
            attendance = Attendance.query.filter_by(user_id=user.id, course_id=course_id, attendance_date=attendance_date).first()
            if attendance:
                attendance.status = status
                db.session.commit()
            else:
                attendance = Attendance(user_id=user.id, course_id=course_id, attendance_date=attendance_date, status=status)
                db.session.add(attendance)
                db.session.commit()
        return redirect(url_for('view_course', course_id=course.id))
    return render_template('mark_attendance.html', course=course, users=users)
#------------------------------- Unused Code End -------------------------------------------#

@app.route('/courses/<int:course_id>/topics/<int:topic_id>/upload', methods=["GET","POST"])
def upload(course_id,topic_id):
    if 'user_id' not in session or session['user_id']==None:
        return redirect('/login')
    
    if request.method=='POST':
        file = request.files['file']
        filename = secure_filename(file.filename)
        save_location='static/uploads/' +"_"+ str(course_id) +"_"+ str(topic_id) + "_" + filename
        file.save(save_location)
        link='uploads/' +"_"+ str(course_id) +"_"+ str(topic_id) + "_" + filename
        upload = Upload(topic_id=topic_id,link_to_file=link)
        db.session.add(upload)
        db.session.commit()
        topic = Topic.query.get(topic_id)
        return redirect(url_for('view_topic',course_id=course_id,topic_id=topic_id))

    if request.method=='GET':
        topic = Topic.query.get(topic_id)
        return render_template("upload.html",course_id=course_id,topic_id=topic_id,topic=topic)
    
@app.route('/logout')
def logout():
    if 'user_id' not in session or session['user_id']==None:
        return redirect('/login')
    
    session.clear()
    flash("Logged Out Successfully")
    return redirect(url_for('login'))


#-------------------------------------------------------------- App Run --------------------------------------------------#

if __name__=="__main__":
    create_admin()  # Creates admin When Database Is Created
    app.run(debug=True,host="0.0.0.0",port=8082)    # Remove Debugging options When Deploying the Project