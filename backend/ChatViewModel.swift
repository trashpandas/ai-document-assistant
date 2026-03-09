// ChatViewModel.swift
// Manages chat state, sends messages to the backend, handles document uploads,
// and polls for processing status.

import Foundation
import Combine
import SwiftUI
import UIKit

// MARK: - Data Models

struct ChatMessage: Identifiable {
    let id = UUID()
    let content: String
    let isUser: Bool
    let sources: [String]
    let pdfURLs: [String: String]  // filename -> "/pdf/filename"
    let timestamp = Date()
}

struct DocumentInfo: Codable {
    let filename: String
    let characters: Int
    let pageCount: Int

    enum CodingKeys: String, CodingKey {
        case filename
        case characters
        case pageCount = "page_count"
    }

    init(filename: String, characters: Int, pageCount: Int = 0) {
        self.filename = filename
        self.characters = characters
        self.pageCount = pageCount
    }
}

// MARK: - View Model

class ChatViewModel: ObservableObject {
    @Published var messages: [ChatMessage] = []
    @Published var inputText: String = ""
    @Published var isLoading: Bool = false
    @Published var isProcessing: Bool = false
    @Published var processingMessage: String = ""
    @Published var uploadedDocuments: [DocumentInfo] = []

    private var conversationHistory: [[String: String]] = []
    private var processingTimer: Timer?

    init() {
        messages.append(ChatMessage(
            content: "Welcome! Upload a document using the paperclip button, then ask me anything about it. This version uses AI-powered analysis with smart search to find the most relevant sections.",
            isUser: false,
            sources: [],
            pdfURLs: [:]
        ))
        fetchDocuments()
    }

    func clearChat() {
        messages = [ChatMessage(
            content: "Welcome! Upload a document using the paperclip button, then ask me anything about it.",
            isUser: false,
            sources: [],
            pdfURLs: [:]
        )]
        conversationHistory = []
    }

    func saveConversation() {
        guard !conversationHistory.isEmpty else { return }

        var text = "AI Document Assistant — Conversation Log\n"
        text += "Date: \(Date().formatted())\n"
        text += String(repeating: "=", count: 50) + "\n\n"

        for turn in conversationHistory {
            let label = turn["role"] == "user" ? "You" : "Assistant"
            text += "\(label):\n\(turn["content"] ?? "")\n\n"
            text += String(repeating: "-", count: 40) + "\n\n"
        }

        // Use the share sheet to save/share
        let activityVC = UIActivityViewController(activityItems: [text], applicationActivities: nil)
        if let windowScene = UIApplication.shared.connectedScenes.first as? UIWindowScene,
           let rootVC = windowScene.windows.first?.rootViewController {
            rootVC.present(activityVC, animated: true)
        }
    }

    func sendMessage() {
        let text = inputText.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !text.isEmpty, !isLoading else { return }

        inputText = ""
        messages.append(ChatMessage(content: text, isUser: true, sources: [], pdfURLs: [:]))
        isLoading = true

        let payload: [String: Any] = [
            "message": text,
            "conversation_history": conversationHistory
        ]

        APIService.post(endpoint: "/chat", payload: payload) { [weak self] result in
            DispatchQueue.main.async {
                guard let self = self else { return }
                self.isLoading = false

                switch result {
                case .success(let data):
                    if let reply = data["reply"] as? String {
                        let sources = data["sources"] as? [String] ?? []
                        let pdfURLs = data["pdf_urls"] as? [String: String] ?? [:]
                        self.messages.append(ChatMessage(
                            content: reply,
                            isUser: false,
                            sources: sources,
                            pdfURLs: pdfURLs
                        ))
                        self.conversationHistory.append(["role": "user", "content": text])
                        self.conversationHistory.append(["role": "assistant", "content": reply])
                    } else if let error = data["error"] as? String {
                        self.messages.append(ChatMessage(
                            content: "Error: \(error)", isUser: false, sources: [], pdfURLs: [:]
                        ))
                    }
                case .failure(let error):
                    self.messages.append(ChatMessage(
                        content: "Could not reach the server. Is it running?\n\(error.localizedDescription)",
                        isUser: false,
                        sources: [],
                        pdfURLs: [:]
                    ))
                }
            }
        }
    }

    func uploadDocument(filename: String, data: Data) {
        messages.append(ChatMessage(
            content: "Uploading \"\(filename)\"... This may take a minute for PDFs (each page is analyzed by AI).",
            isUser: false, sources: [], pdfURLs: [:]
        ))

        APIService.upload(endpoint: "/upload", filename: filename, data: data) { [weak self] result in
            DispatchQueue.main.async {
                guard let self = self else { return }

                switch result {
                case .success(let responseData):
                    if let message = responseData["message"] as? String {
                        self.messages.append(ChatMessage(
                            content: message,
                            isUser: false,
                            sources: [],
                            pdfURLs: [:]
                        ))
                        // Start polling for processing status
                        self.startProcessingPoll(filename: filename)
                    }
                case .failure(let error):
                    self.messages.append(ChatMessage(
                        content: "Upload failed: \(error.localizedDescription)",
                        isUser: false,
                        sources: [],
                        pdfURLs: [:]
                    ))
                }
            }
        }
    }

    // MARK: - Processing Status Polling

    private func startProcessingPoll(filename: String) {
        isProcessing = true
        processingMessage = "Processing \"\(filename)\"..."

        processingTimer?.invalidate()
        processingTimer = Timer.scheduledTimer(withTimeInterval: 2.0, repeats: true) { [weak self] _ in
            self?.checkProcessingStatus(filename: filename)
        }
    }

    private func checkProcessingStatus(filename: String) {
        APIService.get(endpoint: "/documents/status") { [weak self] result in
            DispatchQueue.main.async {
                guard let self = self else { return }

                if case .success(let data) = result,
                   let fileStatus = data[filename] as? [String: Any] {
                    let status = fileStatus["status"] as? String ?? ""
                    let message = fileStatus["message"] as? String ?? ""

                    self.processingMessage = message

                    if status == "done" {
                        self.processingTimer?.invalidate()
                        self.processingTimer = nil
                        self.isProcessing = false
                        self.messages.append(ChatMessage(
                            content: "\"\(filename)\" is ready! \(message). You can now ask questions about it.",
                            isUser: false, sources: [], pdfURLs: [:]
                        ))
                        self.fetchDocuments()
                    } else if status == "error" {
                        self.processingTimer?.invalidate()
                        self.processingTimer = nil
                        self.isProcessing = false
                        self.messages.append(ChatMessage(
                            content: "Error processing \"\(filename)\": \(message)",
                            isUser: false, sources: [], pdfURLs: [:]
                        ))
                    }
                }
            }
        }
    }

    func fetchDocuments() {
        APIService.get(endpoint: "/documents") { [weak self] result in
            DispatchQueue.main.async {
                if case .success(let data) = result,
                   let docs = data["documents"] as? [[String: Any]] {
                    self?.uploadedDocuments = docs.compactMap { dict in
                        guard let filename = dict["filename"] as? String,
                              let characters = dict["characters"] as? Int else { return nil }
                        let pageCount = dict["page_count"] as? Int ?? 0
                        return DocumentInfo(filename: filename, characters: characters, pageCount: pageCount)
                    }
                }
            }
        }
    }
}
