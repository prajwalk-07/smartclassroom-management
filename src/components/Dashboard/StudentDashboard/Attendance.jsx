import React, { useState, useEffect } from 'react';

import {
  Box,
  Paper,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Typography,
  CircularProgress,
  Button,
  Alert,
  Card,
  CardContent
} from '@mui/material';
import {
  CheckCircle as CheckCircleIcon,
  Class as ClassIcon,
  Person as PersonIcon,
  Schedule as ScheduleIcon
} from '@mui/icons-material';
import axios from 'axios';

const Attendance = () => {
  const [attendance, setAttendance] = useState([]);
  const [currentClass, setCurrentClass] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [successMessage, setSuccessMessage] = useState('');

  useEffect(() => {
    fetchAttendance();
    fetchCurrentClass();
    // Refresh current class every minute
    const interval = setInterval(fetchCurrentClass, 60000);
    return () => clearInterval(interval);
  }, []);

  const fetchCurrentClass = async () => {
    try {
      const user = JSON.parse(localStorage.getItem('user'));
      if (!user || !user.role_id) {
        throw new Error('User data not found');
      }

      const response = await axios.get(`http://localhost:5000/current-class`, {
        params: { student_id: user.role_id }
      });

      if (response.data.status === 'success') {
        // Ensure is_present is properly set as a boolean
        const classData = {
          ...response.data.data,
          is_present: Boolean(response.data.data.is_present)
        };
        setCurrentClass(classData);
        setError('');
      } else {
        setCurrentClass(null);
      }
    } catch (err) {
      console.error('Error fetching current class:', err);
      setCurrentClass(null);
    }
  };

  const fetchAttendance = async () => {
    try {
      const user = JSON.parse(localStorage.getItem('user'));
      if (!user || !user.role_id) {
        throw new Error('User data not found');
      }

      const response = await axios.get(`http://localhost:5000/student/attendance`, {
        params: { student_id: user.role_id }
      });

      if (response.data.status === 'success') {
        setAttendance(response.data.data);
      } else {
        setError('Failed to fetch attendance data');
      }
    } catch (err) {
      console.error('Error fetching attendance:', err);
      setError(err.message || 'Failed to fetch attendance data');
    } finally {
      setLoading(false);
    }
  };
  // Current problematic code
  const markPresent = async () => {
    try {
      const user = JSON.parse(localStorage.getItem('user'));
      if (!user || !user.role_id || !currentClass) {
        throw new Error('Required information not found');
      }
  
      // Add validation for required fields
      if (!currentClass.subject_id || !currentClass.teacher_id) {
        throw new Error('Missing class or teacher information');
      }
  
      setLoading(true);
      setError('');
  
      const requestData = {
        student_id: user.role_id,
        subject_id: currentClass.subject_id,
        teacher_id: currentClass.teacher_id
      };
  
      // Log the request data for debugging
      console.log('Sending attendance request:', requestData);
  
      const response = await axios.post('http://localhost:5000/attendance/request', requestData);
  
      if (response.data.status === 'success') {
        setSuccessMessage('Attendance request sent to teacher successfully!');
        setCurrentClass(prev => ({
          ...prev,
          attendance_status: 'pending'
        }));
      }
    } catch (err) {
      console.error('Error requesting attendance:', err);
      setError(err.response?.data?.message || 'Failed to request attendance');
      setTimeout(() => setError(''), 3000);
    } finally {
      setLoading(false);
    }
  };

  return (
    <Box sx={{ p: 2 }}>
    {error && (
      <Alert severity="error" sx={{ mb: 2 }}>
        {error}
      </Alert>
    )}
    {successMessage && (
      <Alert severity="success" sx={{ mb: 2 }}>
        {successMessage}
      </Alert>
    )}
    
    {currentClass ? (
      <Card>
        <CardContent>
          <Typography variant="h6" gutterBottom>
            Current Class: {currentClass.subject_name}
          </Typography>
          <Typography color="textSecondary">
            Teacher: {currentClass.teacher_name}
          </Typography>
          <Typography color="textSecondary">
            Time: {currentClass.formatted_start_time} - {currentClass.formatted_end_time}
          </Typography>
          <Button
            variant="contained"
            color="primary"
            onClick={markPresent}
            disabled={loading || 
                     currentClass.is_present || 
                     currentClass.attendance_status === 'pending'}
            sx={{ mt: 2 }}
            fullWidth
          >
            {currentClass.is_present ? 'Already Marked Present' :
             currentClass.attendance_status === 'pending' ? 'Request Pending' :
             'Request Attendance'}
          </Button>
        </CardContent>
      </Card>
    ) : (
      <Typography>No ongoing class at the moment</Typography>
    )}
      {/* Attendance History Table */}
      <Typography variant="h5" gutterBottom>
        Attendance Record
      </Typography>

      {loading ? (
        <Box sx={{ display: 'flex', justifyContent: 'center', m: 3 }}>
          <CircularProgress />
        </Box>
      ) : error ? (
        <Typography color="error" sx={{ m: 2 }}>
          {error}
        </Typography>
      ) : (
        <TableContainer component={Paper}>
          <Table>
            <TableHead>
              <TableRow>
                <TableCell>Date</TableCell>
                <TableCell>Subject</TableCell>
                <TableCell>Status</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {attendance.map((record, index) => (
                <TableRow 
                  key={index}
                  sx={{
                    backgroundColor: record.status === 1 ? 
                      'rgba(76, 175, 80, 0.1)' : 'rgba(244, 67, 54, 0.1)'
                  }}
                >
                  <TableCell>{record.date}</TableCell>
                  <TableCell>{record.subject}</TableCell>
                  <TableCell>
                    <Box
                      sx={{
                        display: 'inline-block',
                        px: 2,
                        py: 0.5,
                        borderRadius: 1,
                        backgroundColor: record.status === 1 ? 
                          'rgba(76, 175, 80, 0.2)' : 'rgba(244, 67, 54, 0.2)',
                        color: record.status === 1 ? 'success.dark' : 'error.dark'
                      }}
                    >
                      {record.status === 1 ? 'Present' : 'Absent'}
                    </Box>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </TableContainer>
      )}
    </Box>
  );
};

export default Attendance;