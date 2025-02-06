# propKhoj

## Overview
propKhoj is a real estate application designed to facilitate property searches and manage conversations with potential buyers, sellers, and agents. It leverages AI to enhance user interactions and streamline property management.

## Getting Started

### Prerequisites
- Docker
- Docker Compose

### Setup

1. **Build the Docker Images**

   To build the Docker images without using the cache, run:
   ```bash
   docker-compose -f docker-compose.base.yml build --no-cache
   ```

2. **Start the Application**

   To start the application, use:
   ```bash
   docker-compose -f docker-compose.base.yml up
   ```

3. **Access the Shell**

   For accessing the Django shell or bash within the backend container, use:
   ```bash
   docker-compose -f docker-compose.base.yml run backend python manage.py shell
   docker-compose -f docker-compose.base.yml run backend bash
   ```

## Usage

- **Property Management**: Manage and search for properties using the provided API endpoints.
- **Chat Functionality**: Engage in conversations with AI assistance to facilitate real estate transactions.

## Contributing

We welcome contributions! Please fork the repository and submit a pull request for any enhancements or bug fixes.

## License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.

## Contact

For any inquiries or support, please contact [support@propkhoj.com](mailto:support@propkhoj.com).