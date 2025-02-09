import React, { useState, useEffect } from 'react';
import {
  Box,
  Paper,
  Typography,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Select,
  MenuItem,
  FormControl,
  InputLabel,
  Button,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Alert,
  Chip
} from '@mui/material';
import axios from 'axios';

const AssignmentManagement = () => {
  const [students, setStudents] = useState([]);
  const [selectedStudent, setSelectedStudent] = useState('');
  const [assignments, setAssignments] = useState([]);
  const [showSubmissionDialog, setShowSubmissionDialog] = useState(false);
  const [submissionDetails, setSubmissionDetails] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    fetchStudents();
  }, []);

  const getTeacherInfo = () => {
    const userStr = localStorage.getItem("user");
    if (!userStr) {
      setError("Please log in again");
      return null;
    }
    const userData = JSON.parse(userStr);
    if (!userData.role_id) {
      setError("Teacher information not found");
      return null;
    }
    return userData;
  };

  const fetchStudents = async () => {
    try {
      const user = getTeacherInfo();
      if (!user) return;

      const response = await axios.get(
        `http://localhost:5000/teacher/students`,
        {
          params: {
            user_id: user.id,
          },
        }
      );

      if (response.data.status === "success") {
        setStudents(response.data.data);
      } else {
        console.error("Failed to fetch students:", response.data.message);
        setError("Failed to fetch students");
      }
    } catch (error) {
      console.error("Error fetching students:", error);
      setError(
        "Error fetching students: " +
          (error.response?.data?.message || error.message)
      );
    }
  };

  const fetchStudentAssignments = async (studentId) => {
    try {
      const user = getTeacherInfo();
      if (!user) return;

      const response = await axios.get(
        `http://localhost:5000/student/assignments`,
        {
          params: {
            student_id: studentId,
            teacher_id: user.role_id
          }
        }
      );

      if (response.data.status === "success") {
        setAssignments(response.data.data);
      } else {
        console.error("Failed to fetch assignments:", response.data.message);
        setError("Failed to fetch assignments");
      }
    } catch (error) {
      console.error("Error fetching assignments:", error);
      setError(
        "Error fetching assignments: " +
          (error.response?.data?.message || error.message)
      );
    }
  };

  const handleStudentChange = (event) => {
    setSelectedStudent(event.target.value);
    fetchStudentAssignments(event.target.value);
  };

  const handleViewSubmission = async (assignment) => {
    try {
      const user = getTeacherInfo();
      if (!user) return;

      const response = await axios.get(
        `http://localhost:5000/assignment/submission-details/${assignment.id}`,
        {
          params: {
            student_id: selectedStudent,
            teacher_id: user.role_id
          }
        }
      );

      if (response.data.status === "success") {
        setSubmissionDetails(response.data.data);
        setShowSubmissionDialog(true);
      } else {
        setError("Failed to fetch submission details");
      }
    } catch (error) {
      console.error("Error fetching submission details:", error);
      setError(
        "Error fetching submission details: " +
          (error.response?.data?.message || error.message)
      );
    }
  };

  return (
    <Box>
      <Typography variant="h5" gutterBottom>
        Assignment Management
      </Typography>

      {error && (
        <Alert severity="error" sx={{ mb: 2 }}>
          {error}
        </Alert>
      )}

      <FormControl fullWidth sx={{ mb: 3 }}>
        <InputLabel>Select Student</InputLabel>
        <Select
          value={selectedStudent}
          label="Select Student"
          onChange={handleStudentChange}
        >
          {students.map((student) => (
            <MenuItem key={student.id} value={student.id}>
              {student.name} - {student.roll_number}
            </MenuItem>
          ))}
        </Select>
      </FormControl>

      {selectedStudent && (
        <TableContainer component={Paper}>
          <Table>
            <TableHead>
              <TableRow>
                <TableCell>Title</TableCell>
                <TableCell>Subject</TableCell>
                <TableCell>Due Date</TableCell>
                <TableCell>Status</TableCell>
                <TableCell>Actions</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {assignments.map((assignment) => (
                <TableRow key={assignment.id}>
                  <TableCell>{assignment.title}</TableCell>
                  <TableCell>{assignment.subject_name}</TableCell>
                  <TableCell>
                    {new Date(assignment.due_date).toLocaleDateString()}
                  </TableCell>
                  <TableCell>
            <Chip
              label={assignment.submission_status}
              color={assignment.status_color}
              size="small"
            />
          </TableCell>
                  <TableCell>
                    <Button
                      variant="contained"
                      size="small"
                      onClick={() => handleViewSubmission(assignment)}
                      disabled={assignment.submission_status === 'Not Submitted'}
                    >
                      View Submission
                    </Button>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </TableContainer>
      )}

      <Dialog
        open={showSubmissionDialog}
        onClose={() => setShowSubmissionDialog(false)}
        maxWidth="md"
        fullWidth
      >
        <DialogTitle>Assignment Submission Details</DialogTitle>
        <DialogContent>
          {submissionDetails && (
            <Box>
              <Typography variant="h6">{submissionDetails.title}</Typography>
              <Typography>Subject: {submissionDetails.subject_name}</Typography>
              <Typography>Due Date: {new Date(submissionDetails.due_date).toLocaleString()}</Typography>
              <Typography>Submission Date: {new Date(submissionDetails.submission_date).toLocaleString()}</Typography>
              <Typography>Status: {submissionDetails.submission_status}</Typography>
              {submissionDetails.file_path && (
                <Button
                  variant="contained"
                  href={`http://localhost:5000/uploads/${submissionDetails.file_path}`}
                  target="_blank"
                  sx={{ mt: 2 }}
                >
                  View Submission File
                </Button>
              )}
            </Box>
          )}
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setShowSubmissionDialog(false)}>Close</Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
};

export default AssignmentManagement;