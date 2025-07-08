﻿using System;
using System.Collections.Generic;
using System.Linq;
using System.Net;
using System.Net.Sockets;
using System.Text;
using System.Threading;
using System.Threading.Tasks;
using Rhino;
using Rhino.Commands;
using Rhino.Geometry;
using Rhino.Input;
using Rhino.Input.Custom;
using Rhino.UI;
using Newtonsoft.Json;
using Newtonsoft.Json.Linq;
using static System.Runtime.InteropServices.JavaScript.JSType;
using System.Text.Json;
using Rhino.DocObjects;
using rhinomcp.Serializers;
using JsonException = Newtonsoft.Json.JsonException;
using Eto.Forms;
using RhinoMCPPlugin.Functions;

namespace RhinoMCPPlugin
{
    public class RhinoMCPServer
    {
        private string host;
        private int port;
        private bool running;
        private TcpListener listener;
        private Thread serverThread;
        private readonly object lockObject = new object();
        private RhinoMCPFunctions handler;
        private TcpClient client;

        public RhinoMCPServer(string host = "127.0.0.1", int port = 1999)
        {
            this.host = host;
            this.port = port;
            this.running = false;
            this.listener = null;
            this.serverThread = null;
            this.handler = new RhinoMCPFunctions();
        }


        public void Start()
        {
            lock (lockObject)
            {
                if (running)
                {
                    RhinoApp.WriteLine("Server is already running");
                    return;
                }

                running = true;
            }

            try
            {
                // Create TCP listener
                IPAddress ipAddress = IPAddress.Parse(host);
                listener = new TcpListener(ipAddress, port);
                listener.Start();

                // Start server thread
                serverThread = new Thread(ServerLoop);
                serverThread.IsBackground = true;
                serverThread.Start();

                RhinoDoc.AddRhinoObject += OnRhinoObjectAdded;
                RhinoDoc.DeleteRhinoObject += OnRhinoObjectDeleted;

                RhinoApp.WriteLine($"RhinoMCP server started on {host}:{port}");
            }
            catch (Exception e)
            {
                RhinoApp.WriteLine($"Failed to start server: {e.Message}");
                Stop();
            }
        }

        public void Stop()
        {
            lock (lockObject)
            {
                running = false;
            }

            // Close listener
            if (listener != null)
            {
                try
                {
                    listener.Stop();
                }
                catch
                {
                    // Ignore errors on closing
                }
                listener = null;
            }

            // Wait for thread to finish
            if (serverThread != null && serverThread.IsAlive)
            {
                try
                {
                    serverThread.Join(1000); // Wait up to 1 second
                }
                catch
                {
                    // Ignore errors on join
                }
                serverThread = null;
            }

            RhinoDoc.AddRhinoObject -= OnRhinoObjectAdded;
            RhinoDoc.DeleteRhinoObject -= OnRhinoObjectDeleted;

            RhinoApp.WriteLine("RhinoMCP server stopped");
        }

        private void OnRhinoObjectAdded(object sender, RhinoObjectEventArgs e)
        {
            if (client == null || !client.Connected) return;

            var rhinoObject = e.TheObject;
            var baseObjectInfo = Serializer.RhinoObject(rhinoObject);
            
            // Enhance with geometric analysis
            var enhancedObjectInfo = GeometricAnalysis.AnalyzeGeometry(rhinoObject.Geometry, baseObjectInfo);

            var message = new JObject
            {
                ["type"] = "event",
                ["event"] = "object_created",
                ["data"] = enhancedObjectInfo
            };

            try
            {
                var stream = client.GetStream();
                var responseBytes = Encoding.UTF8.GetBytes(message.ToString(Formatting.None));
                stream.Write(responseBytes, 0, responseBytes.Length);
            }
            catch (Exception ex)
            {
                RhinoApp.WriteLine($"Failed to send object creation event: {ex.Message}");
            }
        }

        private void OnRhinoObjectDeleted(object sender, RhinoObjectEventArgs e)
        {
            if (client == null || !client.Connected) return;

            var rhinoObject = e.TheObject;
            var message = new JObject
            {
                ["type"] = "event",
                ["event"] = "object_deleted",
                ["data"] = new JObject
                {
                    ["id"] = rhinoObject.Id.ToString(),
                    ["name"] = rhinoObject.Name
                }
            };

            try
            {
                var stream = client.GetStream();
                var responseBytes = Encoding.UTF8.GetBytes(message.ToString(Formatting.None));
                stream.Write(responseBytes, 0, responseBytes.Length);
            }
            catch (Exception ex)
            {
                RhinoApp.WriteLine($"Failed to send object deletion event: {ex.Message}");
            }
        }

        private void ServerLoop()
        {
            RhinoApp.WriteLine("Server thread started");

            while (IsRunning())
            {
                try
                {
                    // Set a timeout to check running condition periodically
                    listener.Server.ReceiveTimeout = 1000;
                    listener.Server.SendTimeout = 1000;

                    // Wait for client connection
                    if (listener.Pending())
                    {
                        this.client = listener.AcceptTcpClient();
                        RhinoApp.WriteLine($"Connected to client: {client.Client.RemoteEndPoint}");

                        // Handle client in a separate thread
                        Thread clientThread = new Thread(() => HandleClient(client));
                        clientThread.IsBackground = true;
                        clientThread.Start();
                    }
                    else
                    {
                        // No pending connections, sleep a bit to prevent CPU overuse
                        Thread.Sleep(100);
                    }
                }
                catch (Exception e)
                {
                    RhinoApp.WriteLine($"Error in server loop: {e.Message}");

                    if (!IsRunning())
                        break;

                    Thread.Sleep(500);
                }
            }

            RhinoApp.WriteLine("Server thread stopped");
        }

        private bool IsRunning()
        {
            lock (lockObject)
            {
                return running;
            }
        }

        private void HandleClient(TcpClient client)
        {
            RhinoApp.WriteLine("Client handler started");

            byte[] buffer = new byte[8192];
            string incompleteData = string.Empty;

            try
            {
                NetworkStream stream = client.GetStream();

                while (IsRunning())
                {
                    try
                    {
                        // Check if there's data available to read
                        if (client.Available > 0 || stream.DataAvailable)
                        {
                            int bytesRead = stream.Read(buffer, 0, buffer.Length);
                            if (bytesRead == 0)
                            {
                                RhinoApp.WriteLine("Client disconnected");
                                break;
                            }

                            string data = Encoding.UTF8.GetString(buffer, 0, bytesRead);
                            incompleteData += data;

                            try
                            {
                                // Try to parse as JSON
                                JObject command = JObject.Parse(incompleteData);
                                incompleteData = string.Empty;

                                // Execute command on Rhino's main thread
                                RhinoApp.InvokeOnUiThread(new Action(() =>
                                {
                                    try
                                    {
                                        JObject response = ExecuteCommand(command);
                                        string responseJson = JsonConvert.SerializeObject(response);

                                        try
                                        {
                                            byte[] responseBytes = Encoding.UTF8.GetBytes(responseJson);
                                            stream.Write(responseBytes, 0, responseBytes.Length);
                                        }
                                        catch
                                        {
                                            RhinoApp.WriteLine("Failed to send response - client disconnected");
                                        }
                                    }
                                    catch (Exception e)
                                    {
                                        RhinoApp.WriteLine($"Error executing command: {e.Message}");
                                        try
                                        {
                                            JObject errorResponse = new JObject
                                            {
                                                ["status"] = "error",
                                                ["message"] = e.Message
                                            };

                                            byte[] errorBytes = Encoding.UTF8.GetBytes(errorResponse.ToString());
                                            stream.Write(errorBytes, 0, errorBytes.Length);
                                        }
                                        catch
                                        {
                                            // Ignore send errors
                                        }
                                    }
                                }));
                            }
                            catch (JsonException)
                            {
                                // Incomplete JSON data, wait for more
                            }
                        }
                        else
                        {
                            // No data available, sleep a bit to prevent CPU overuse
                            Thread.Sleep(50);
                        }
                    }
                    catch (Exception e)
                    {
                        RhinoApp.WriteLine($"Error receiving data: {e.Message}");
                        break;
                    }
                }
            }
            catch (Exception e)
            {
                RhinoApp.WriteLine($"Error in client handler: {e.Message}");
            }
            finally
            {
                try
                {
                    client.Close();
                }
                catch
                {
                    // Ignore errors on close
                }
                RhinoApp.WriteLine("Client handler stopped");
            }
        }

        private JObject ExecuteCommand(JObject command)
        {
            try
            {
                string cmdType = command["type"]?.ToString();
                string requestId = command["request_id"]?.ToString();
                JObject parameters = command["params"] as JObject ?? new JObject();

                RhinoApp.WriteLine($"Executing command: {cmdType}");

                JObject result = ExecuteCommandInternal(cmdType, parameters);

                if (requestId != null)
                {
                    result["request_id"] = requestId;
                }

                RhinoApp.WriteLine("Command execution complete");
                return result;
            }
            catch (Exception e)
            {
                RhinoApp.WriteLine($"Error executing command: {e.Message}");
                return new JObject
                {
                    ["status"] = "error",
                    ["message"] = e.Message
                };
            }
        }

        private JObject ExecuteCommandInternal(string cmdType, JObject parameters)
        {

            // Dictionary to map command types to handler methods
            Dictionary<string, Func<JObject, JObject>> handlers = new Dictionary<string, Func<JObject, JObject>>
            {
                ["get_document_info"] = this.handler.GetDocumentInfo,
                ["create_object"] = this.handler.CreateObject,
                ["create_objects"] = this.handler.CreateObjects,
                ["get_object_info"] = this.handler.GetObjectInfo,
                ["get_selected_objects_info"] = this.handler.GetSelectedObjectsInfo,
                ["delete_object"] = this.handler.DeleteObject,
                ["modify_object"] = this.handler.ModifyObject,
                ["modify_objects"] = this.handler.ModifyObjects,
                ["execute_rhinoscript_python_code"] = this.handler.ExecuteRhinoscript,
                ["select_objects"] = this.handler.SelectObjects,
                ["create_layer"] = this.handler.CreateLayer,
                ["get_or_set_current_layer"] = this.handler.GetOrSetCurrentLayer,
                ["delete_layer"] = this.handler.DeleteLayer
                // Add more handlers as needed
            };

            if (handlers.TryGetValue(cmdType, out var handler))
            {
                var doc = RhinoDoc.ActiveDoc;
                var record = doc.BeginUndoRecord("Run MCP command");
                try
                {
                    JObject result = handler(parameters);
                    return new JObject
                    {
                        ["status"] = "success",
                        ["result"] = result
                    };
                }
                catch (Exception e)
                {
                    RhinoApp.WriteLine($"Error in handler: {e.Message}");
                    return new JObject
                    {
                        ["status"] = "error",
                        ["message"] = e.Message
                    };
                }
                finally
                {
                    doc.EndUndoRecord(record);
                }
            }
            else
            {
                return new JObject
                {
                    ["status"] = "error",
                    ["message"] = $"Unknown command type: {cmdType}"
                };
            }
        }
    }
}