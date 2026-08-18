## Overview

The **Automation Project** includes two main modules:
1. **Optimizer**: Manages complex scheduling constraints (e.g., resource availability, time constraints, capacibility, session length, gaps,group constraints) and uses constraint programming to find optimal solutions.
2. **Solution Generator**: Generates possible scheduling solutions based on available data, identifies unmatched events, refines constraints, and categorizes events based on priorities.

## Features
- **Dynamic Event Scheduling**: Schedules resources dynamically based on time, availability, and constraints.
- **Drive Time Optimization**: Calculates and integrates travel times into the scheduling process.
- **Flexible Constraints**: Supports a variety of constraints like time, frequency, breaks, and session lengths.
- **Real-Time Updates**: The application allows for real-time updates to the scheduling process.
- **Error Handling and Logging**: Detailed error handling and logging for better debugging and monitoring.
- **Modular Components**: Easy to extend with additional optimization rules and constraints.

## Technologies
- **Flask**: A lightweight web framework for building the API endpoints.
- **Docker**: Used for containerization and deploying the application.
- **Google Maps API**: For calculating distances and durations between addresses.
- **Python 3.x**: The main programming language for the backend logic.
- **OR-Tools (CP-SAT solver)**: For constraint programming and optimization of schedules.

## Prerequisites
- **Docker**: Required for containerization and easy deployment.
- **Python 3.x** (Recommended 3.9 or higher)
- **Google Maps API Key** for driving time calculations.

Ensure you have the following environment variables set:
- `GOOGLE_API_KEY`: Your Google Maps API key.
- `FLASK_ENV`: Set to `development` for local development.
- `FLASK_APP`: The Flask application entry point (e.g., `app2.py`).
- `BACKEND_URL`: The backend API URL (e.g., `https://production-api.abaschedules.com/api`).

Need .asw.env file with credentials for access to AWS

## Setup and Installation

1. **Clone the repository**:

```bash
git clone https://github.com/ABA-Schedules/automation.git
cd automation
```
2. **Set up environment variables**:

- ask to developer to provide .env file and .aws.env file

3. **Install Dependencies**

```bash
pip install -r requirements.txt
```
4. **Set up Docker**

```bash
docker compose up --build
```
5. **Running Application**

```bash
docker compose up
```

## API Endpoints

### POST `/optimizer/test_insert`
- **Description**: To call test_insert_handler for the optimizer.
- **Request Body**: JSON payload containing event data.
- **Response**: Confirmation message or error if the process fails.

### POST `/optimizer/solution_generator`
- **Description**: Generates optimized schedules based on the provided data.
- **Request Body**: Contains scheduling data including date range, resources, settings, and constraints.
- **Response**: JSON containing the optimized schedules.

### POST `/optimizer/automation`
- **Description**: Runs the optimizer process for event scheduling(day, week).
- **Request Body**: Contains scheduling data and constraints.
- **Response**: Optimized event schedule or error message.

### **Contributing**  
   Outline how developers can contribute to the project, including forking, creating branches, and submitting pull requests.

```markdown
We welcome contributions to this project! To contribute:

1. Fork the repository.
2. Create a new branch from develop branch (`git checkout -b feature-name`).
3. Make your changes.
4. Commit your changes (`git commit -am 'Add new feature'`).
5. Push to the branch (`git push origin feature-name`).
6. Open a pull request.