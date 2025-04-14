from flask import Flask, request, jsonify
from flask_cors import CORS
import mysql.connector
from datetime import datetime
import cv2
import numpy as np
import logging
from twilio.rest import Client
import requests
import json
from werkzeug.security import  check_password_hash
import os
from werkzeug.utils import secure_filename
app = Flask(__name__)
CORS(app)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
TWILIO_ACCOUNT_SID = ''
TWILIO_AUTH_TOKEN = ''
TWILIO_PHONE_NUMBER = ''
API_KEY = ''
twilio_client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
# DB_CONFIG = {
#     'host': 'localhost',
#     'user': 'root',
#     'password': '',
#     'database': 'smart_classroom'
# }
DB_CONFIG = {
     'host': '',
    'user': '',
    'password': '',
    'database': '',
    'port': ,
}
def get_db_connection():
    try:
        return mysql.connector.connect(**DB_CONFIG)
    except Exception as e:
        logger.error(f"Database connection error: {e}")
        raise

@app.route('/student/recovery-assignments', methods=['GET'])
def get_recovery_assignments():
    try:
        student_id = request.args.get('student_id')
        if not student_id:
            return jsonify({
                "status": "error",
                "message": "Student ID is required"
            }), 400

        db = get_db_connection()
        cursor = db.cursor(dictionary=True)
        cursor.execute("""
            WITH ConsecutiveAbsences AS (
                SELECT 
                    a.subject_id,
                    s.name as subject_name,
                    s.code as subject_code,
                    COUNT(*) as absent_count,
                    GROUP_CONCAT(a.date ORDER BY a.date) as absent_dates
                FROM attendance a
                JOIN subjects s ON a.subject_id = s.id
                WHERE a.student_id = %s 
                    AND a.status = 0 
                    AND a.date >= DATE_SUB(CURDATE(), INTERVAL 7 DAY)
                GROUP BY a.subject_id
                HAVING COUNT(*) >= 3
            )
            SELECT * FROM ConsecutiveAbsences
        """, (student_id,))
        
        absent_subjects = cursor.fetchall()
        assignments_list = []
        for subject in absent_subjects:
            cursor.execute("""
                SELECT 
                    a.id,
                    a.title,
                    a.description,
                    a.due_date,
                    s.name as subject_name,
                    s.code as subject_code,
                    COALESCE(sub.id IS NOT NULL, FALSE) as is_submitted
                FROM assignments a
                JOIN subjects s ON a.subject_id = s.id
                LEFT JOIN assignment_submissions sub ON a.id = sub.assignment_id 
                    AND sub.student_id = %s
                WHERE a.subject_id = %s
                AND a.created_at >= DATE_SUB(CURDATE(), INTERVAL 7 DAY)
            """, (student_id, subject['subject_id']))

            existing_assignment = cursor.fetchone()

            if not existing_assignment:
                prompt = f"""Generate 5 random questions about {subject['subject_name']}.
                Include a mix of:
                - Easy questions (basic understanding)
                - Medium questions (application-based)
                - Hard questions (analysis and problem-solving)
                Make each question different in difficulty and concept.
                Return only the questions, one per line."""

                try:
                    headers = {
                        "Content-Type": "application/json",
                        "Authorization": f"Bearer {API_KEY}"
                    }

                    payload = {
                        "model": "nvidia/llama-3.1-nemotron-70b-instruct",
                        "messages": [
                            {
                                "role": "system",
                                "content": "You are a question generator specializing in creating educational questions."
                            },
                            {
                                "role": "user",
                                "content": prompt
                            }
                        ],
                        "temperature": 1.2,
                        "max_tokens": 1000
                    }

                    response = requests.post(
                        "https://integrate.api.nvidia.com/v1/chat/completions",
                        headers=headers,
                        json=payload,
                        timeout=30
                    )

                    if response.status_code == 200:
                        questions = response.json()['choices'][0]['message']['content'].strip().split('\n')
                        questions = [q.strip() for q in questions if q.strip()][:11]

                        cursor.execute("""
                            INSERT INTO assignments 
                            (subject_id, title, description, due_date, status)
                            VALUES (%s, %s, %s, DATE_ADD(CURDATE(), INTERVAL 7 DAY), 'pending')
                        """, (
                            subject['subject_id'],
                            f"Recovery Assignment - {subject['subject_name']}",
                            json.dumps(questions)
                        ))
                        db.commit()

                        cursor.execute("""
                            SELECT 
                                a.id,
                                a.title,
                                a.description,
                                a.due_date,
                                s.name as subject_name,
                                s.code as subject_code,
                                FALSE as is_submitted
                            FROM assignments a
                            JOIN subjects s ON a.subject_id = s.id
                            WHERE a.id = LAST_INSERT_ID()
                        """)
                        new_assignment = cursor.fetchone()
                        if new_assignment:
                            new_assignment['questions'] = questions
                            assignments_list.append(new_assignment)

                except Exception as e:
                    logger.error(f"Error generating questions: {e}")
                    continue
            else:
     
                existing_assignment['questions'] = json.loads(existing_assignment['description'])
                assignments_list.append(existing_assignment)

        return jsonify({
            "status": "success",
            "data": assignments_list
        })

    except Exception as e:
        logger.error(f"Error in recovery assignments: {e}")
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500
    finally:
        if 'cursor' in locals():
            cursor.close()
        if 'db' in locals():
            db.close()
@app.route('/attendance/request', methods=['POST'])
def request_attendance():
    try:
        data = request.json
        student_id = data.get('student_id')
        subject_id = data.get('subject_id')
        teacher_id = data.get('teacher_id')

    
        if not student_id:
            return jsonify({
                "status": "error",
                "message": "Student ID is required"
            }), 400
        
        if not subject_id:
            return jsonify({
                "status": "error",
                "message": "Subject ID is required"
            }), 400
            
        if not teacher_id:
            return jsonify({
                "status": "error",
                "message": "Teacher ID is required"
            }), 400

        db = get_db_connection()
        cursor = db.cursor(dictionary=True)

        cursor.execute("""
            INSERT INTO attendance_requests 
            (student_id, subject_id, class_date, teacher_id)
            VALUES (%s, %s, CURDATE(), %s)
        """, (student_id, subject_id, teacher_id))

        db.commit()
        cursor.close()
        db.close()

        return jsonify({
            "status": "success",
            "message": "Attendance request submitted successfully"
        })

    except Exception as e:
        logger.error(f"Error requesting attendance: {e}")
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500
@app.route('/current-class', methods=['GET'])
def get_current_class_endpoint():
    try:
        student_id = request.args.get('student_id')
        if not student_id:
            return jsonify({
                "status": "error",
                "message": "Student ID is required"
            }), 400

        db = get_db_connection()
        cursor = db.cursor(dictionary=True)

        current_day = datetime.now().weekday() + 1  # 1=Monday, 7=Sunday
        current_time = datetime.now().strftime('%H:%M:%S')

        cursor.execute("""
            SELECT 
                s.id as subject_id,
                s.name as subject_name,
                s.code as subject_code,
                t.id as teacher_id,
                t.name as teacher_name,
                ss.start_time,
                ss.end_time,
                TIME_FORMAT(ss.start_time, '%h:%i %p') as formatted_start_time,
                TIME_FORMAT(ss.end_time, '%h:%i %p') as formatted_end_time,
                COALESCE(a.status, 0) as is_present,
                COALESCE(ar.status, NULL) as attendance_status
            FROM students st
            JOIN subjects s ON s.class_id = st.class_id
            JOIN teachers t ON s.teacher_id = t.id
            JOIN subject_schedule ss ON s.id = ss.subject_id
            LEFT JOIN attendance a ON a.subject_id = s.id 
                AND a.student_id = st.id 
                AND a.date = CURDATE()
            LEFT JOIN attendance_requests ar ON ar.subject_id = s.id
                AND ar.student_id = st.id
                AND ar.class_date = CURDATE()
            WHERE st.id = %s
                AND ss.day_of_week = %s
                AND %s BETWEEN ss.start_time AND ss.end_time
        """, (student_id, current_day, current_time))
        
        current_class = cursor.fetchone()
        
        if current_class:
            return jsonify({
                "status": "success",
                "data": {
                    "subject_id": current_class['subject_id'],
                    "subject_name": current_class['subject_name'],
                    "subject_code": current_class['subject_code'],
                    "teacher_id": current_class['teacher_id'],
                    "teacher_name": current_class['teacher_name'],
                    "formatted_start_time": current_class['formatted_start_time'],
                    "formatted_end_time": current_class['formatted_end_time'],
                    "is_present": bool(current_class['is_present']),
                    "attendance_status": current_class['attendance_status']
                }
            })
        else:
            return jsonify({
                "status": "error",
                "message": "No ongoing class found"
            }), 404

    except Exception as e:
        logger.error(f"Error getting current class: {e}")
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500

@app.route('/attendance/mark-present', methods=['POST'])
def mark_attendance():
    try:
        data = request.json
        student_id = data.get('student_id')
        class_id = data.get('class_id')

        if not all([student_id, class_id]):
            return jsonify({
                "status": "error",
                "message": "Student ID and Class ID are required"
            }), 400
        current_class = get_current_class(class_id)
        if not current_class:
            return jsonify({
                "status": "error",
                "message": "No ongoing class found"
            }), 404

        db = get_db_connection()
        cursor = db.cursor(dictionary=True)
        cursor.execute("""
            SELECT id, status 
            FROM attendance 
            WHERE student_id = %s 
            AND subject_id = %s 
            AND date = CURRENT_DATE()
        """, (student_id, current_class['subject_id']))
        
        existing_attendance = cursor.fetchone()

        if existing_attendance:
            cursor.execute("""
                UPDATE attendance 
                SET status = 1 
                WHERE id = %s
            """, (existing_attendance['id'],))
        else:
            cursor.execute("""
                INSERT INTO attendance (student_id, subject_id, date, status)
                VALUES (%s, %s, CURRENT_DATE(), 1)
            """, (student_id, current_class['subject_id']))

        db.commit()
        cursor.close()
        db.close()

        return jsonify({
            "status": "success",
            "message": "Attendance marked successfully",
            "data": {
                "subject": current_class['subject_name'],
                "teacher": current_class['teacher_name'],
                "time": f"{current_class['formatted_start_time']} - {current_class['formatted_end_time']}"
            }
        })

    except Exception as e:
        logger.error(f"Error marking attendance: {e}")
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500
@app.route('/student/course-recommendations', methods=['GET'])
def get_course_recommendations():
    try:
        student_id = request.args.get('student_id')
        if not student_id:
            return jsonify({
                "status": "error",
                "message": "Student ID is required"
            }), 400

        db = get_db_connection()
        cursor = db.cursor(dictionary=True)
        cursor.execute("""
            SELECT 
                s.name as subject_name,
                s.code as subject_code,
                CAST(AVG((ia.marks_obtained/ia.total_marks) * 100) AS DECIMAL(5,2)) as percentage
            FROM internal_assessments ia
            JOIN subjects s ON ia.subject_id = s.id
            WHERE ia.student_id = %s
            GROUP BY s.name, s.code
        """, (student_id,))

        performance = cursor.fetchall()

        if not performance:
            return jsonify({
                "status": "error",
                "message": "No performance data found"
            }), 404

        recommendations = {}
        for subject in performance:
            percentage = float(subject['percentage']) if subject['percentage'] else 0
            subject_name = subject['subject_name']
            if percentage < 60:
                level = "Beginner"
                courses = get_beginner_courses(subject_name)
            elif percentage < 75:
                level = "Intermediate"
                courses = get_intermediate_courses(subject_name)
            else:
                level = "Advanced"
                courses = get_advanced_courses(subject_name)

            recommendations[subject_name] = {
                "performance": percentage,
                "level": level,
                "courses": courses
            }

        return jsonify({
            "status": "success",
            "data": {
                "recommendations": recommendations
            }
        })

    except Exception as e:
        logger.error(f"Error generating course recommendations: {e}")
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500
@app.route('/teacher/attendance-requests', methods=['GET'])
def get_attendance_requests():
    try:
        teacher_id = request.args.get('teacher_id')
        date = request.args.get('date')

        if not teacher_id or not date:
            return jsonify({
                "status": "error",
                "message": "Teacher ID and date are required"
            }), 400

        db = get_db_connection()
        cursor = db.cursor(dictionary=True)

        cursor.execute("""
            SELECT 
                ar.id,
                ar.student_id,
                ar.subject_id,
                ar.status,
                ar.request_time,
                s.name as student_name,
                sub.name as subject_name
            FROM attendance_requests ar
            JOIN students s ON ar.student_id = s.id
            JOIN subjects sub ON ar.subject_id = sub.id
            WHERE sub.teacher_id = %s 
            AND DATE(ar.class_date) = %s
            ORDER BY ar.request_time DESC
        """, (teacher_id, date))

        requests = cursor.fetchall()
        
        return jsonify({
            "status": "success",
            "data": requests
        })

    except Exception as e:
        logger.error(f"Error fetching attendance requests: {e}")
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500
    finally:
        if 'cursor' in locals():
            cursor.close()
        if 'db' in locals():
            db.close()
@app.route('/store-monitoring-log', methods=['POST'])
def store_monitoring_log():
    try:
        data = request.json
        student_id = data.get('student_id')
        subject_id = data.get('subject_id')
        status = data.get('status')

        if not all([student_id, subject_id, status]):
            return jsonify({
                "status": "error",
                "message": "Missing required parameters"
            }), 400

        db = get_db_connection()
        cursor = db.cursor()

        cursor.execute("""
            INSERT INTO class_monitoring_logs 
            (student_id, subject_id, status) 
            VALUES (%s, %s, %s)
        """, (student_id, subject_id, status))

        db.commit()
        cursor.close()
        db.close()

        return jsonify({
            "status": "success",
            "message": "Monitoring log stored successfully"
        })

    except Exception as e:
        logger.error(f"Error storing monitoring log: {e}")
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500
@app.route('/teacher/students', methods=['GET'])
def get_teacher_students():
    try:
        user_id = request.args.get('user_id')
        if not user_id:
            return jsonify({
                "status": "error",
                "message": "User ID is required"
            }), 400

        db = get_db_connection()
        cursor = db.cursor(dictionary=True)

        cursor.execute("""
            SELECT t.id as teacher_id
            FROM teachers t
            JOIN users u ON t.user_id = u.id
            WHERE u.id = %s
        """, (user_id,))
        
        teacher = cursor.fetchone()
        if not teacher:
            return jsonify({
                "status": "error",
                "message": "Teacher not found"
            }), 404

        cursor.execute("""
            SELECT DISTINCT 
                s.id,
                s.name,
                s.roll_number,
                s.class_id
            FROM students s
            JOIN subjects sub ON s.class_id = sub.class_id
            WHERE sub.teacher_id = %s
            ORDER BY s.name
        """, (teacher['teacher_id'],))

        students = cursor.fetchall()

        return jsonify({
            "status": "success",
            "data": students
        })

    except Exception as e:
        logger.error(f"Error fetching teacher's students: {e}")
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500
    finally:
        if 'cursor' in locals():
            cursor.close()
        if 'db' in locals():
            db.close()
@app.route('/teacher/monitoring-logs', methods=['GET'])
def get_monitoring_logs():
    try:
        student_id = request.args.get('student_id')
        subject_id = request.args.get('subject_id')
        date = request.args.get('date')
        teacher_id = request.args.get('teacher_id')

        if not all([student_id, subject_id, date, teacher_id]):
            return jsonify({
                "status": "error",
                "message": "Missing required parameters"
            }), 400

        db = get_db_connection()
        cursor = db.cursor(dictionary=True)


        query = """
            SELECT 
                cml.id,
                cml.status,
                cml.timestamp
            FROM class_monitoring_logs cml
            JOIN subjects s ON cml.subject_id = s.id
            WHERE cml.student_id = %s
            AND cml.subject_id = %s
            AND s.teacher_id = %s
            AND DATE(cml.timestamp) = %s
            ORDER BY cml.timestamp DESC
        """
        
        # Convert parameters to correct types
        params = (
            int(student_id),
            int(subject_id),
            int(teacher_id),
            date
        )
        
        print("Query:", query)
        print("Parameters:", params)
        
        cursor.execute(query, params)
        logs = cursor.fetchall()

        # Format timestamp after fetching
        formatted_logs = []
        for log in logs:
            formatted_logs.append({
                'id': log['id'],
                'status': log['status'],
                'timestamp': log['timestamp'].strftime('%Y-%m-%d %H:%M:%S') if log['timestamp'] else None
            })

        return jsonify({
            "status": "success",
            "data": formatted_logs if formatted_logs else []
        })

    except Exception as e:
        logger.error(f"Error fetching monitoring logs: {e}")
        print(f"Detailed error: {str(e)}")
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500
    finally:
        if 'cursor' in locals():
            cursor.close()
        if 'db' in locals():
            db.close()
@app.route('/assignment/submission-details/<int:assignment_id>', methods=['GET'])
def get_submission_details(assignment_id):
    try:
        student_id = request.args.get('student_id')
        teacher_id = request.args.get('teacher_id')

        if not all([student_id, teacher_id]):
            return jsonify({
                "status": "error",
                "message": "Student ID and Teacher ID are required"
            }), 400

        db = get_db_connection()
        cursor = db.cursor(dictionary=True)

        query = """
            SELECT 
                asub.id as submission_id,
                asub.file_path,
                asub.submission_date,
                asub.status as submission_status,
                a.title,
                a.description,
                a.due_date,
                s.name as subject_name
            FROM assignments a
            JOIN subjects s ON a.subject_id = s.id
            LEFT JOIN assignment_submissions asub 
                ON a.id = asub.assignment_id 
                AND asub.student_id = %s
            WHERE a.id = %s 
            AND s.teacher_id = %s
        """

        cursor.execute(query, (student_id, assignment_id, teacher_id))
        submission = cursor.fetchone()

        if submission:
            if submission['submission_date']:
                submission['submission_date'] = submission['submission_date'].strftime('%Y-%m-%d %H:%M:%S')
            if submission['due_date']:
                submission['due_date'] = submission['due_date'].strftime('%Y-%m-%d %H:%M:%S')

        return jsonify({
            "status": "success",
            "data": submission
        })

    except Exception as e:
        logger.error(f"Error fetching submission details: {e}")
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500
    finally:
        if 'cursor' in locals():
            cursor.close()
        if 'db' in locals():
            db.close()
@app.route('/student/assignments', methods=['GET'])
def get_student_assignments():
    try:
        student_id = request.args.get('student_id')
        teacher_id = request.args.get('teacher_id')
        
        if not all([student_id, teacher_id]):
            return jsonify({
                "status": "error",
                "message": "Student ID and Teacher ID are required"
            }), 400

        db = get_db_connection()
        cursor = db.cursor(dictionary=True)

        # Updated query to include both assignment and submission status
        query = """
            SELECT 
                a.id,
                a.title,
                a.description,
                a.due_date,
                a.status as assignment_status,
                s.name as subject_name,
                s.id as subject_id,
                CASE 
                    WHEN asub.id IS NOT NULL THEN 
                        CASE 
                            WHEN asub.status = 'reviewed' THEN 'Completed'
                            ELSE 'Pending Review'
                        END
                    WHEN a.due_date < NOW() THEN 'Overdue'
                    ELSE 'Not Submitted'
                END as submission_status,
                asub.submission_date,
                asub.file_path,
                asub.status as review_status
            FROM assignments a
            INNER JOIN subjects s ON a.subject_id = s.id
            LEFT JOIN assignment_submissions asub ON 
                a.id = asub.assignment_id AND 
                asub.student_id = %s
            WHERE s.teacher_id = %s
            ORDER BY 
                CASE 
                    WHEN asub.status = 'pending' THEN 1
                    WHEN asub.id IS NULL AND a.due_date >= NOW() THEN 2
                    WHEN asub.status = 'reviewed' THEN 3
                    ELSE 4
                END,
                a.due_date DESC
        """

        cursor.execute(query, (student_id, teacher_id))
        assignments = cursor.fetchall()

        # Format dates and process status
        for assignment in assignments:
            if assignment['due_date']:
                assignment['due_date'] = assignment['due_date'].strftime('%Y-%m-%d %H:%M:%S')
            if assignment['submission_date']:
                assignment['submission_date'] = assignment['submission_date'].strftime('%Y-%m-%d %H:%M:%S')
            
            # Add color coding for status
            assignment['status_color'] = {
                'Completed': 'success',
                'Pending Review': 'warning',
                'Not Submitted': 'info',
                'Overdue': 'error'
            }.get(assignment['submission_status'], 'default')

        return jsonify({
            "status": "success",
            "data": assignments
        })

    except Exception as e:
        logger.error(f"Error fetching student assignments: {e}")
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500
    finally:
        if 'cursor' in locals():
            cursor.close()
        if 'db' in locals():
            db.close()
@app.route('/teacher/respond-attendance', methods=['POST'])
def respond_to_attendance():
    try:
        data = request.json
        request_id = data.get('request_id')
        status = data.get('status')
        teacher_id = data.get('teacher_id')

        if not all([request_id, status, teacher_id]):
            return jsonify({
                "status": "error",
                "message": "Request ID, status, and teacher ID are required"
            }), 400

        if status not in ['approved', 'rejected']:
            return jsonify({
                "status": "error",
                "message": "Invalid status"
            }), 400

        db = get_db_connection()
        cursor = db.cursor(dictionary=True)

        # First verify the request exists and belongs to this teacher
        cursor.execute("""
            SELECT ar.*, s.teacher_id, s.name as subject_name, s.id as subject_id,
                   ss.start_time, ss.end_time
            FROM attendance_requests ar
            JOIN subjects s ON ar.subject_id = s.id
            JOIN subject_schedule ss ON s.id = ss.subject_id
            WHERE ar.id = %s AND s.teacher_id = %s
        """, (request_id, teacher_id))
        
        attendance_request = cursor.fetchone()
        if not attendance_request:
            return jsonify({
                "status": "error",
                "message": "Attendance request not found or unauthorized"
            }), 404

        # Update the attendance request
        cursor.execute("""
            UPDATE attendance_requests 
            SET status = %s, 
                response_time = CURRENT_TIMESTAMP,
                teacher_id = %s
            WHERE id = %s
        """, (status, teacher_id, request_id))

        # Handle attendance record
        attendance_status = 1 if status == 'approved' else 0
        
        cursor.execute("""
            INSERT INTO attendance 
            (student_id, subject_id, date, status)
            VALUES (%s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE status = VALUES(status)
        """, (
            attendance_request['student_id'],
            attendance_request['subject_id'],
            attendance_request['class_date'],
            attendance_status
        ))

        # If rejected, check for 3 consecutive absences
        if status == 'rejected':
            cursor.execute("""
                SELECT COUNT(*) as absent_count,
                       s.id as student_id, s.name as student_name,
                       s.student_phone, s.parent_phone
                FROM attendance a
                JOIN students s ON a.student_id = s.id
                WHERE a.student_id = %s 
                AND a.subject_id = %s
                AND a.status = 0
                AND a.date >= DATE_SUB(%s, INTERVAL 3 DAY)
                GROUP BY s.id
            """, (
                attendance_request['student_id'],
                attendance_request['subject_id'],
                attendance_request['class_date']
            ))
            
            result = cursor.fetchone()
            
            if result and result['absent_count'] >= 3:
                try:
                    client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
                    
                    # Shorter messages for both student and parent
                    student_message = (
                        f"Alert: You missed {attendance_request['subject_name']} for 3 days. "
                        f"Complete recovery assignment before deadline."
                    )

                    parent_message = (
                        f"Alert: {result['student_name']} has missed "
                        f"{attendance_request['subject_name']} for 3 consecutive days."
                    )

                    # Send student message
                    if result['student_phone']:
                        student_phone = result['student_phone']
                        if not student_phone.startswith('+'):
                            student_phone = '+' + student_phone

                        logger.info(f"Sending to student: {student_phone}")
                        try:
                            message = client.messages.create(
                                body=student_message,
                                from_=TWILIO_PHONE_NUMBER,
                                to=student_phone
                            )
                            logger.info(f"Student message sent: {message.sid}")
                        except Exception as e:
                            logger.error(f"Student message failed: {str(e)}")

                    # Send parent message
                    if result['parent_phone']:
                        parent_phone = result['parent_phone']
                        if not parent_phone.startswith('+'):
                            parent_phone = '+' + parent_phone

                        logger.info(f"Sending to parent: {parent_phone}")
                        try:
                            message = client.messages.create(
                                body=parent_message,
                                from_=TWILIO_PHONE_NUMBER,
                                to=parent_phone
                            )
                            logger.info(f"Parent message sent: {message.sid}")
                        except Exception as e:
                            logger.error(f"Parent message failed: {str(e)}")

                except Exception as e:
                    logger.error(f"SMS notification error: {str(e)}")

        db.commit()

        return jsonify({
            "status": "success",
            "message": f"Attendance request {status} successfully"
        })

    except Exception as e:
        logger.error(f"Error responding to attendance request: {e}")
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500
    finally:
        if 'cursor' in locals():
            cursor.close()
        if 'db' in locals():
            db.close()
def get_beginner_courses(subject):
    courses = [
        {
            "title": f"Introduction to {subject}",
            "platform": "freeCodeCamp",
            "difficulty": "Beginner",
            "description": f"Learn the fundamentals of {subject} with hands-on practice",
            "url": f"https://www.freecodecamp.org/learn/{subject.lower().replace(' ', '-')}"
        },
        {
            "title": f"{subject} Basics",
            "platform": "W3Schools",
            "difficulty": "Beginner",
            "description": f"Step-by-step guide to {subject} fundamentals",
            "url": f"https://www.w3schools.com/{subject.lower().replace(' ', '')}"
        },
        {
            "title": f"Getting Started with {subject}",
            "platform": "MDN Web Docs",
            "difficulty": "Beginner",
            "description": f"Comprehensive guide to {subject} for beginners",
            "url": f"https://developer.mozilla.org/en-US/docs/Learn/{subject.lower().replace(' ', '_')}"
        }
    ]
    return courses

def get_intermediate_courses(subject):
    courses = [
        {
            "title": f"Intermediate {subject}",
            "platform": "edX",
            "difficulty": "Intermediate",
            "description": f"Deepen your understanding of {subject} concepts",
            "url": f"https://www.edx.org/learn/{subject.lower().replace(' ', '-')}"
        },
        {
            "title": f"Professional {subject} Development",
            "platform": "Codecademy",
            "difficulty": "Intermediate",
            "description": f"Build professional {subject} skills",
            "url": f"https://www.codecademy.com/learn/{subject.lower().replace(' ', '-')}"
        },
        {
            "title": f"{subject} in Practice",
            "platform": "GeeksforGeeks",
            "difficulty": "Intermediate",
            "description": f"Practice-oriented {subject} learning",
            "url": f"https://www.geeksforgeeks.org/{subject.lower().replace(' ', '-')}"
        }
    ]
    return courses

def get_advanced_courses(subject):
    courses = [
        {
            "title": f"Advanced {subject} Concepts",
            "platform": "MIT OpenCourseWare",
            "difficulty": "Advanced",
            "description": f"Master advanced {subject} topics",
            "url": f"https://ocw.mit.edu/search/?q={subject.lower().replace(' ', '+')}"
        },
        {
            "title": f"Expert {subject} Techniques",
            "platform": "Stanford Online",
            "difficulty": "Advanced",
            "description": f"Advanced {subject} methodologies and best practices",
            "url": f"https://online.stanford.edu/search-catalog?query={subject.lower().replace(' ', '+')}"
        },
        {
            "title": f"{subject} Mastery",
            "platform": "Khan Academy",
            "difficulty": "Advanced",
            "description": f"Complete mastery of {subject} concepts",
            "url": f"https://www.khanacademy.org/search?query={subject.lower().replace(' ', '+')}"
        }
    ]
    return courses
def get_current_class(class_id):
    """
    Get details of the currently ongoing class for a given class_id
    """
    try:
        days = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
        
        db = get_db_connection()
        cursor = db.cursor(dictionary=True)
        current_time = datetime.now().strftime('%I:%M %p')
        current_day = datetime.now().strftime('%A')
        current_weekday = datetime.now().weekday() + 1
        
        print("\n=== ONGOING CLASS DETAILS ===")
        print(f"Current Time: {current_time}")
        print(f"Current Day: {current_day}")
        print(f"Weekday Number: {current_weekday}")
        print(f"Class ID being checked: {class_id}")
        print("============================")

        cursor.execute("""
            SELECT 
                s.id as subject_id,
                s.name as subject_name,
                s.code as subject_code,
                t.name as teacher_name,
                t.id as teacher_id,
                TIME_FORMAT(ss.start_time, '%h:%i %p') as formatted_start_time,
                TIME_FORMAT(ss.end_time, '%h:%i %p') as formatted_end_time,
                ss.day_of_week
            FROM subject_schedule ss
            JOIN subjects s ON ss.subject_id = s.id
            LEFT JOIN teachers t ON s.teacher_id = t.id
            WHERE s.class_id = %s 
            AND ss.day_of_week = WEEKDAY(CURRENT_DATE()) + 1
            AND CURRENT_TIME() BETWEEN ss.start_time AND ss.end_time
            LIMIT 1
        """, (class_id,))
        
        class_info = cursor.fetchone()
        
        if class_info:
            class_info['day_name'] = days[class_info['day_of_week'] - 1]

            print("\n=== FOUND CLASS DETAILS ===")
            print(f"Subject: {class_info['subject_name']} ({class_info['subject_code']})")
            print(f"Teacher: {class_info['teacher_name']}")
            print(f"Time: {class_info['formatted_start_time']} - {class_info['formatted_end_time']}")
            print(f"Day: {class_info['day_name']}")
            print("==========================\n")
        else:
            print("\n=== NO ONGOING CLASS FOUND ===")
            print("Checking database for schedule...")
            cursor.execute("""
                SELECT 
                    s.name as subject_name,
                    ss.day_of_week,
                    TIME_FORMAT(ss.start_time, '%h:%i %p') as formatted_start_time,
                    TIME_FORMAT(ss.end_time, '%h:%i %p') as formatted_end_time
                FROM subject_schedule ss
                JOIN subjects s ON ss.subject_id = s.id
                WHERE s.class_id = %s
                ORDER BY ss.day_of_week, ss.start_time
            """, (class_id,))
            
            all_schedules = cursor.fetchall()
            if all_schedules:
                print("\nAll scheduled classes for this class_id:")
                for schedule in all_schedules:
                    day_name = days[schedule['day_of_week'] - 1]
                    print(f"{schedule['subject_name']} on {day_name}: "
                          f"{schedule['formatted_start_time']} - {schedule['formatted_end_time']}")
            else:
                print("No schedule found for this class_id")
            print("============================\n")

        return class_info

    except Exception as e:
        print("\n=== ERROR OCCURRED ===")
        print(f"Error fetching current class: {e}")
        print("=====================\n")
        logger.error(f"Error fetching current class: {e}")
        return None
    finally:
        if 'cursor' in locals():
            cursor.close()
        if 'db' in locals():
            db.close()
get_current_class(1)
@app.route('/login', methods=['POST'])
def login():
    try:
        data = request.json
        email = data.get('email')
        password = data.get('password')
        role = data.get('role')

        # Validate required fields
        if not all([email, password, role]):
            return jsonify({
                "status": "error",
                "message": "Email, password and role are required"
            }), 400

        db = get_db_connection()
        cursor = db.cursor(dictionary=True)

        # Get user with the specified email and role
        cursor.execute("""
            SELECT 
                u.id,
                u.email,
                u.password,
                u.role,
                CASE 
                    WHEN u.role = 'student' THEN s.id 
                    WHEN u.role = 'teacher' THEN t.id 
                END as role_id,
                CASE 
                    WHEN u.role = 'student' THEN s.name 
                    WHEN u.role = 'teacher' THEN t.name 
                END as name,
                CASE 
                    WHEN u.role = 'student' THEN s.class_id 
                    ELSE NULL 
                END as class_id
            FROM users u
            LEFT JOIN students s ON u.id = s.user_id AND u.role = 'student'
            LEFT JOIN teachers t ON u.id = t.user_id AND u.role = 'teacher'
            WHERE u.email = %s AND u.role = %s
        """, (email, role))
        
        user = cursor.fetchone()

        # Check if user exists and password matches
        if not user:
            return jsonify({
                "status": "error",
                "message": "User not found"
            }), 401

        if not check_password_hash(user['password'], password):
            return jsonify({
                "status": "error",
                "message": "Invalid password"
            }), 401

        # Create user object for response
        user_data = {
            "id": user['id'],
            "role_id": user['role_id'],
            "email": user['email'],
            "name": user['name'],
            "role": user['role']
        }

        if user['role'] == 'student':
            user_data['class_id'] = user['class_id']

        return jsonify({
            "status": "success",
            "message": "Login successful",
            "user": user_data
        })

    except Exception as e:
        logger.error(f"Login error: {e}")
        return jsonify({
            "status": "error",
            "message": "An error occurred during login"
        }), 500
    finally:
        if 'cursor' in locals():
            cursor.close()
        if 'db' in locals():
            db.close()
def generate_session_token(user_id):
   
    return f"session_{user_id}_{datetime.now().timestamp()}"
@app.route('/student/attendance', methods=['GET'])
def get_student_attendance():
    try:
        student_id = request.args.get('student_id')
        if not student_id:
            return jsonify({
                "status": "error",
                "message": "Student ID is required"
            }), 400

        db = get_db_connection()
        cursor = db.cursor(dictionary=True)

        cursor.execute("""
            SELECT 
                DATE_FORMAT(a.date, '%Y-%m-%d') as date,
                s.name as subject,
                a.status
            FROM attendance a
            JOIN subjects s ON a.subject_id = s.id
            WHERE a.student_id = %s
            ORDER BY a.date DESC
        """, (student_id,))

        attendance_records = cursor.fetchall()
        formatted_records = [{
            'date': record['date'],
            'subject': record['subject'],
            'status': int(record['status'])  # Ensure status is an integer
        } for record in attendance_records]

        return jsonify({
            "status": "success",
            "data": formatted_records
        })

    except Exception as e:
        logger.error(f"Error fetching attendance: {e}")
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500
    finally:
        if 'cursor' in locals():
            cursor.close()
        if 'db' in locals():
            db.close()
@app.route('/analyze-stream', methods=['POST'])
def analyze_stream():
    try:
        print("\n=== STARTING STREAM ANALYSIS ===")
        
        if 'image' not in request.files:
            print("No image provided in request")
            return jsonify({"status": "error", "message": "No image provided"}), 400

        file = request.files['image']
        student_id = request.form.get('student_id')
        inactivity_count = int(request.form.get('inactivity_count', 0))
        
        print(f"Student ID: {student_id}")
        print(f"Inactivity Count: {inactivity_count}")

        npimg = np.frombuffer(file.read(), np.uint8)
        img = cv2.imdecode(npimg, cv2.COLOR_BGR2GRAY)

        face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')
        eye_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_eye.xml')

        faces = face_cascade.detectMultiScale(img, 1.3, 5)
        is_active = False

        for (x, y, w, h) in faces:
            roi_gray = img[y:y+h, x:x+w]
            eyes = eye_cascade.detectMultiScale(roi_gray)
            if len(eyes) >= 2:
                is_active = True
                break

        print(f"Activity Detection Result: {'Active' if is_active else 'Inactive'}")
        
        notification_sent = False
        notification_message = ""
        if not is_active:
            print(f"Student inactive. Current count: {inactivity_count}")
        
        if not is_active and inactivity_count >= 5:
            print("\n=== INACTIVITY THRESHOLD REACHED ===")
            try:
                db = get_db_connection()
                cursor = db.cursor(dictionary=True)

                print("Getting student and mentor details...")
                # Get student and mentor details
                cursor.execute("""
                    SELECT 
                        s.name as student_name,
                        m.phone_number as mentor_phone,
                        m.name as mentor_name,
                        s.class_id
                    FROM students s
                    JOIN mentors m ON s.mentor_id = m.id
                    WHERE s.id = %s
                """, (student_id,))

                result = cursor.fetchone()
                
                if not result:
                    print(f"No student/mentor found for student_id: {student_id}")
                    logger.error(f"No student or mentor found for student_id: {student_id}")
                    return jsonify({
                        "status": "error",
                        "message": "Student or mentor not found"
                    }), 404

                print(f"Found student: {result['student_name']}")
                print(f"Mentor: {result['mentor_name']}")
                print(f"Mentor phone: {result['mentor_phone']}")

                if result['mentor_phone']:
                    print("Getting current class information...")
                    current_class = get_current_class(result['class_id'])
                    
                    if current_class:
                        print(f"Current class found: {current_class['subject_name']}")
                        sms_message = (
                            f"STUDENT INACTIVITY ALERT!\n"
                            f"Student: {result['student_name']}\n"
                            f"Current Class: {current_class['subject_name']} ({current_class['subject_code']})\n"
                            f"Teacher: {current_class['teacher_name']}\n"
                            f"Class Time: {current_class['formatted_start_time']} - {current_class['formatted_end_time']}\n"
                            f"Alert Time: {datetime.now().strftime('%I:%M %p')}\n"
                            f"Status: Student has been inactive for 5 consecutive checks."
                        )
                    else:
                        print("No current class found")
                        sms_message = (
                            f"STUDENT INACTIVITY ALERT!\n"
                            f"Student: {result['student_name']}\n"
                            f"Time: {datetime.now().strftime('%I:%M %p')}\n"
                            f"Status: Student has been inactive for 5 consecutive checks.\n"
                            f"Note: No scheduled class found at this time."
                        )

                    print("\n=== SENDING SMS NOTIFICATION ===")
                    print(f"To: {result['mentor_name']} ({result['mentor_phone']})")
                    print("Message Content:")
                    print("------------------------")
                    print(sms_message)
                    print("------------------------")

                    try:
                        message = twilio_client.messages.create(
                            from_=TWILIO_PHONE_NUMBER,
                            to=result['mentor_phone'],
                            body=sms_message
                        )
                        
                        notification_sent = True
                        notification_message = f"Alert SMS sent to mentor {result['mentor_name']}"
                        print(f"SMS sent successfully!")
                        print(f"Message SID: {message.sid}")
                        print("============================\n")
                        
                        logger.info(f"SMS sent successfully! Message SID: {message.sid}")

                        print("Resetting inactivity count...")
                        cursor.execute("""
                            UPDATE students 
                            SET inactivity_count = 0, last_active = CURRENT_TIMESTAMP 
                            WHERE id = %s
                        """, (student_id,))
                        
                        db.commit()

                    except Exception as e:
                        print("\n=== SMS SENDING FAILED ===")
                        print(f"Error: {str(e)}")
                        print("========================\n")
                        logger.error(f"Failed to send SMS: {e}")
                        return jsonify({
                            "status": "error",
                            "message": f"Failed to send SMS: {str(e)}"
                        }), 500

            except Exception as e:
                print(f"\n=== DATABASE ERROR ===")
                print(f"Error: {str(e)}")
                print("====================\n")
                logger.error(f"Database error: {e}")
                return jsonify({
                    "status": "error",
                    "message": f"Database error: {str(e)}"
                }), 500
            finally:
                if 'cursor' in locals():
                    cursor.close()
                if 'db' in locals():
                    db.close()

        print("\n=== ANALYSIS COMPLETE ===")
        print(f"Is Active: {is_active}")
        print(f"Notification Sent: {notification_sent}")
        print("=======================\n")

        return jsonify({
            "status": "success",
            "expression": "active" if is_active else "inactive",
            "message": "Student is active" if is_active else "Inactivity detected",
            "notification_sent": notification_sent,
            "notification_message": notification_message,
            "should_reset": notification_sent
        })

    except Exception as e:
        print("\n=== STREAM ANALYSIS ERROR ===")
        print(f"Error: {str(e)}")
        print("===========================\n")
        logger.error(f"Stream analysis error: {e}")
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500
          

@app.route('/student/check-submission/<int:assignment_id>', methods=['GET'])
def check_submission(assignment_id):
    try:
        student_id = request.args.get('student_id')
        if not student_id:
            return jsonify({
                "status": "error",
                "message": "Student ID is required"
            }), 400

        db = get_db_connection()
        cursor = db.cursor(dictionary=True)

        cursor.execute("""
            SELECT id 
            FROM assignment_submissions 
            WHERE assignment_id = %s AND student_id = %s
        """, (assignment_id, student_id))
        
        submission = cursor.fetchone()
        
        return jsonify({
            "status": "success",
            "submitted": bool(submission)
        })

    except Exception as e:
        logger.error(f"Error checking submission: {e}")
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500
    finally:
        if 'cursor' in locals():
            cursor.close()
        if 'db' in locals():
            db.close()

@app.route('/student/marks', methods=['GET'])
def get_student_marks():
    try:
        student_id = request.args.get('student_id')
        if not student_id:
            return jsonify({
                "status": "error",
                "message": "Student ID is required"
            }), 400

        db = get_db_connection()
        cursor = db.cursor(dictionary=True)

        cursor.execute("""
            SELECT 
                ia.id,
                s.name as subject_name,
                ia.assessment_type,
                ia.marks_obtained,
                ia.total_marks,
                ia.date
            FROM internal_assessments ia
            JOIN subjects s ON ia.subject_id = s.id
            WHERE ia.student_id = %s
            ORDER BY ia.date DESC
        """, (student_id,))

        marks = cursor.fetchall()
        
        return jsonify({
            "status": "success",
            "data": marks
        })

    except Exception as e:
        logger.error(f"Error fetching student marks: {e}")
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500

    finally:
        if 'cursor' in locals():
            cursor.close()
        if 'db' in locals():
            db.close()

@app.route('/student/submit-assignment', methods=['POST'])
def submit_assignment():
    try:
        if 'file' not in request.files:
            return jsonify({
                "status": "error",
                "message": "No file provided"
            }), 400

        file = request.files['file']
        student_id = request.form.get('student_id')
        assignment_id = request.form.get('assignment_id')

        if not all([student_id, assignment_id]):
            return jsonify({
                "status": "error",
                "message": "Missing required fields"
            }), 400

        allowed_extensions = {'.pdf', '.doc', '.docx'}
        file_ext = os.path.splitext(file.filename)[1].lower()
        if file_ext not in allowed_extensions:
            return jsonify({
                "status": "error",
                "message": "Invalid file type. Please upload PDF or DOC/DOCX files only."
            }), 400

        db = get_db_connection()
        cursor = db.cursor(dictionary=True)
        cursor.execute("""
            SELECT id FROM assignment_submissions 
            WHERE assignment_id = %s AND student_id = %s
        """, (assignment_id, student_id))
        
        if cursor.fetchone():
            return jsonify({
                "status": "error",
                "message": "Assignment already submitted"
            }), 400
        filename = secure_filename(f"{student_id}_{assignment_id}_{file.filename}")
        file_path = os.path.join('uploads', filename)
        file.save(file_path)

        try:
            cursor.execute("""
                INSERT INTO assignment_submissions 
                (assignment_id, student_id, file_path, status)
                VALUES (%s, %s, %s, 'submitted')
            """, (assignment_id, student_id, file_path))
            cursor.execute("""
                UPDATE assignments 
                SET status = 'completed'
                WHERE id = %s
            """, (assignment_id,))

            db.commit()

            return jsonify({
                "status": "success",
                "message": "Assignment submitted successfully"
            })

        except Exception as e:
            if os.path.exists(file_path):
                os.remove(file_path)
            raise e

    except Exception as e:
        logger.error(f"Error submitting assignment: {e}")
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500
    finally:
        if 'cursor' in locals():
            cursor.close()
        if 'db' in locals():
            db.close()



if __name__ == '__main__':
    app.run(debug=True, port=5000)
