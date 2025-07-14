// dependency_free_json_listener.cpp - JSON parsing WITHOUT external libraries
#include <iostream>
#include <string>
#include <sys/socket.h>
#include <netinet/in.h>
#include <arpa/inet.h>
#include <unistd.h>
#include <cstring>
#include <chrono>
#include <iomanip>
#include <map>

void print_timestamp() {
    auto now = std::chrono::system_clock::now();
    auto time_t = std::chrono::system_clock::to_time_t(now);
    std::cout << "[" << std::put_time(std::localtime(&time_t), "%H:%M:%S") << "] ";
}

// Simple JSON parser - extracts key-value pairs
std::map<std::string, std::string> parse_json_simple(const std::string& json) {
    std::map<std::string, std::string> result;
    
    if (json.empty() || json[0] != '{') {
        return result;  // Not JSON
    }
    
    size_t pos = 1;  // Skip opening '{'
    
    while (pos < json.length()) {
        // Skip whitespace
        while (pos < json.length() && (json[pos] == ' ' || json[pos] == '\t' || json[pos] == '\n')) {
            pos++;
        }
        
        if (pos >= json.length() || json[pos] == '}') break;
        
        // Find key (should be in quotes)
        if (json[pos] == '"') {
            pos++;  // Skip opening quote
            size_t key_start = pos;
            
            // Find closing quote for key
            while (pos < json.length() && json[pos] != '"') {
                pos++;
            }
            
            if (pos >= json.length()) break;
            
            std::string key = json.substr(key_start, pos - key_start);
            pos++;  // Skip closing quote
            
            // Skip whitespace and colon
            while (pos < json.length() && (json[pos] == ' ' || json[pos] == ':' || json[pos] == '\t')) {
                pos++;
            }
            
            // Get value
            std::string value;
            if (pos < json.length()) {
                if (json[pos] == '"') {
                    // String value
                    pos++;  // Skip opening quote
                    size_t value_start = pos;
                    
                    while (pos < json.length() && json[pos] != '"') {
                        pos++;
                    }
                    
                    if (pos < json.length()) {
                        value = json.substr(value_start, pos - value_start);
                        pos++;  // Skip closing quote
                    }
                } else {
                    // Number or other value
                    size_t value_start = pos;
                    
                    while (pos < json.length() && json[pos] != ',' && json[pos] != '}' && json[pos] != ' ') {
                        pos++;
                    }
                    
                    value = json.substr(value_start, pos - value_start);
                }
                
                result[key] = value;
            }
            
            // Skip comma
            while (pos < json.length() && (json[pos] == ',' || json[pos] == ' ' || json[pos] == '\t')) {
                pos++;
            }
        } else {
            pos++;  // Skip invalid character
        }
    }
    
    return result;
}

void process_json_packet(const std::string& data, const std::string& client_ip, int client_port, int packet_num) {
    print_timestamp();
    std::cout << "📦 PKT#" << packet_num << " FROM " << client_ip << ":" << client_port << std::endl;
    
    auto parsed = parse_json_simple(data);
    
    if (parsed.empty()) {
        std::cout << "     📄 RAW DATA: " << data << std::endl;
    } else {
        std::cout << "     ✅ PARSED JSON:" << std::endl;
        
        // Display common beacon fields with nice formatting
        if (parsed.count("status")) {
            std::cout << "        🚨 Status: " << parsed["status"] << std::endl;
        }
        if (parsed.count("id")) {
            std::cout << "        🏷️  ID: " << parsed["id"] << std::endl;
        }
        if (parsed.count("time")) {
            std::cout << "        ⏰ Time: " << parsed["time"] << std::endl;
        }
        
        // Show any other fields
        for (const auto& [key, value] : parsed) {
            if (key != "status" && key != "id" && key != "time") {
                std::cout << "        📋 " << key << ": " << value << std::endl;
            }
        }
        
        std::cout << "     📄 RAW: " << data << std::endl;
    }
    
    std::cout << "     📏 SIZE: " << data.length() << " bytes" << std::endl;
    std::cout << "═══════════════════════════════════════════\n";
}

int main() {
    std::cout << "🔥 FastPing JSON Beacon Monitor v2.0\n";
    std::cout << "====================================\n";
    std::cout << "📡 Listening on port 9876 for JSON beacons\n";
    std::cout << "🧠 Built-in JSON parser (no dependencies)\n";
    std::cout << "🚀 Press Ctrl+C to stop\n\n";

    // Create socket
    int sock = socket(AF_INET, SOCK_DGRAM, 0);
    if (sock < 0) {
        std::cerr << "❌ Socket creation failed\n";
        return 1;
    }

    // Allow address reuse
    int opt = 1;
    setsockopt(sock, SOL_SOCKET, SO_REUSEADDR, &opt, sizeof(opt));

    sockaddr_in server_addr;
    server_addr.sin_family = AF_INET;
    server_addr.sin_port = htons(9876);
    server_addr.sin_addr.s_addr = INADDR_ANY;

    if (bind(sock, (sockaddr*)&server_addr, sizeof(server_addr)) < 0) {
        std::cerr << "❌ Bind failed\n";
        close(sock);
        return 1;
    }

    char buffer[1024];
    sockaddr_in client_addr;
    socklen_t addr_len = sizeof(client_addr);
    int packet_count = 0;

    while (true) {
        int recv_len = recvfrom(sock, buffer, sizeof(buffer) - 1, 0, 
                               (sockaddr*)&client_addr, &addr_len);
        
        if (recv_len > 0) {
            buffer[recv_len] = '\0';
            packet_count++;
            
            char client_ip[INET_ADDRSTRLEN];
            inet_ntop(AF_INET, &client_addr.sin_addr, client_ip, INET_ADDRSTRLEN);
            
            process_json_packet(std::string(buffer), std::string(client_ip), 
                              ntohs(client_addr.sin_port), packet_count);
        }
    }

    close(sock);
    return 0;
}
