using System;
using System.Collections.Generic;
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
using JsonException = Newtonsoft.Json.JsonException;

namespace rhino_mcp
{
    public class RhinoMCPServer
    {
        private string host;
        private int port;
        private bool running;
        private TcpListener listener;
        private Thread serverThread;
        private readonly object lockObject = new object();

        public RhinoMCPServer(string host = "0.0.0.0", int port = 1999)
        {
            this.host = host;
            this.port = port;
            this.running = false;
            this.listener = null;
            this.serverThread = null;
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

            RhinoApp.WriteLine("RhinoMCP server stopped");
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
                        TcpClient client = listener.AcceptTcpClient();
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
                JObject parameters = command["params"] as JObject ?? new JObject();

                RhinoApp.WriteLine($"Executing command: {cmdType}");

                JObject result = ExecuteCommandInternal(cmdType, parameters);

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
                ["get_scene_info"] = GetSceneInfo,
                ["create_object"] = CreateObject,
                ["get_object_info"] = GetObjectInfo,
                ["delete_object"] = DeleteObject,
                ["modify_object"] = ModifyObject,
                ["execute_code"] = ExecuteCode
                // Add more handlers as needed
            };

            if (handlers.TryGetValue(cmdType, out var handler))
            {
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

        #region Command Handlers

        private JObject GetSceneInfo(JObject parameters)
        {
            RhinoApp.WriteLine("Getting scene info...");

            var doc = RhinoDoc.ActiveDoc;
            var result = new JObject
            {
                ["name"] = doc.Name,
                ["object_count"] = doc.Objects.Count,
                ["objects"] = new JArray()
            };

            // Collect minimal object information (limit to first 10 objects)
            int count = 0;
            foreach (var obj in doc.Objects)
            {
                if (count >= 10)
                    break;

                var objInfo = new JObject
                {
                    ["id"] = obj.Id.ToString(),
                    ["name"] = obj.Name ?? "(unnamed)",
                    ["type"] = obj.ObjectType.ToString()
                };

                // Add location data if applicable
                if (obj.Geometry is GeometryBase geometry)
                {
                    BoundingBox bbox = geometry.GetBoundingBox(true);
                    Point3d center = bbox.Center;

                    objInfo["location"] = new JArray
                    {
                        Math.Round(center.X, 2),
                        Math.Round(center.Y, 2),
                        Math.Round(center.Z, 2)
                    };
                }

                ((JArray)result["objects"]).Add(objInfo);
                count++;
            }

            RhinoApp.WriteLine($"Scene info collected: {count} objects");
            return result;
        }

        private JObject CreateObject(JObject parameters)
        {
            string type = parameters["type"]?.ToString() ?? "CUBE";
            string name = parameters["name"]?.ToString();

            // Parse location, rotation, scale
            double[] location = parameters["location"]?.ToObject<double[]>() ?? new double[] { 0, 0, 0 };
            double[] rotation = parameters["rotation"]?.ToObject<double[]>() ?? new double[] { 0, 0, 0 };
            double[] scale = parameters["scale"]?.ToObject<double[]>() ?? new double[] { 1, 1, 1 };

            Point3d point = new Point3d(location[0], location[1], location[2]);

            var doc = RhinoDoc.ActiveDoc;
            Guid objectId = Guid.Empty;

            switch (type.ToUpper())
            {
                case "CUBE":
                case "BOX":
                    // Create a box centered at the specified point
                    double xSize = scale[0], ySize = scale[1], zSize = scale[2];
                    Box box = new Box(
                        new Plane(point, Vector3d.XAxis, Vector3d.YAxis),
                        new Interval(-xSize / 2, xSize / 2),
                        new Interval(-ySize / 2, ySize / 2),
                        new Interval(-zSize / 2, zSize / 2)
                    );
                    objectId = doc.Objects.AddBox(box);
                    break;

                case "SPHERE":
                    // Create a sphere at the specified point
                    double radius = scale[0]; // Use X scale as radius
                    Sphere sphere = new Sphere(point, radius);
                    objectId = doc.Objects.AddSphere(sphere);
                    break;

                case "PLANE":
                    // Create a plane at the specified point
                    double width = scale[0];
                    double length = scale[1];
                    Plane plane = new Plane(point, Vector3d.ZAxis);
                    Rectangle3d rectangle = new Rectangle3d(
                        plane,
                        new Interval(-width / 2, width / 2),
                        new Interval(-length / 2, length / 2)
                    );
                    objectId = doc.Objects.AddRectangle(rectangle);
                    break;

                case "POINT":
                    // Create a point at the specified location
                    objectId = doc.Objects.AddPoint(point);
                    break;

                default:
                    throw new ArgumentException($"Unsupported object type: {type}");
            }

            if (objectId == Guid.Empty)
                throw new InvalidOperationException("Failed to create object");

            // Set name if provided
            if (!string.IsNullOrEmpty(name))
            {
                var rhinoObject = doc.Objects.Find(objectId);
                if (rhinoObject != null)
                {
                    rhinoObject.Attributes.Name = name;
                    doc.Objects.ModifyAttributes(rhinoObject, rhinoObject.Attributes, true);
                }
            }

            // Update views
            doc.Views.Redraw();

            // Return information about the created object
            var result = new JObject
            {
                ["id"] = objectId.ToString(),
                ["name"] = name ?? "",
                ["type"] = type,
                ["location"] = new JArray { location[0], location[1], location[2] },
                ["rotation"] = new JArray { rotation[0], rotation[1], rotation[2] },
                ["scale"] = new JArray { scale[0], scale[1], scale[2] }
            };

            // Add bounding box info
            var obj = doc.Objects.Find(objectId);
            if (obj != null && obj.Geometry != null)
            {
                BoundingBox bbox = obj.Geometry.GetBoundingBox(true);
                result["world_bounding_box"] = new JArray
                {
                    new JArray { bbox.Min.X, bbox.Min.Y, bbox.Min.Z },
                    new JArray { bbox.Max.X, bbox.Max.Y, bbox.Max.Z }
                };
            }

            return result;
        }

        private JObject GetObjectInfo(JObject parameters)
        {
            string objectId = parameters["id"]?.ToString();
            if (string.IsNullOrEmpty(objectId))
                throw new ArgumentException("Object ID is required");

            var doc = RhinoDoc.ActiveDoc;
            var obj = doc.Objects.Find(new Guid(objectId));

            if (obj == null)
                throw new InvalidOperationException($"Object with ID {objectId} not found");

            var result = new JObject
            {
                ["id"] = obj.Id.ToString(),
                ["name"] = obj.Name ?? "(unnamed)",
                ["type"] = obj.ObjectType.ToString(),
                ["layer"] = obj.Attributes.LayerIndex.ToString()
            };

            // Add geometry-specific information
            if (obj.Geometry != null)
            {
                BoundingBox bbox = obj.Geometry.GetBoundingBox(true);
                Point3d center = bbox.Center;

                result["location"] = new JArray
                {
                    Math.Round(center.X, 2),
                    Math.Round(center.Y, 2),
                    Math.Round(center.Z, 2)
                };

                result["bounding_box"] = new JArray
                {
                    new JArray { bbox.Min.X, bbox.Min.Y, bbox.Min.Z },
                    new JArray { bbox.Max.X, bbox.Max.Y, bbox.Max.Z }
                };
            }

            return result;
        }

        private JObject DeleteObject(JObject parameters)
        {
            string objectId = parameters["id"]?.ToString();
            if (string.IsNullOrEmpty(objectId))
                throw new ArgumentException("Object ID is required");

            var doc = RhinoDoc.ActiveDoc;
            bool success = doc.Objects.Delete(new Guid(objectId), true);

            if (!success)
                throw new InvalidOperationException($"Failed to delete object with ID {objectId}");

            // Update views
            doc.Views.Redraw();

            return new JObject
            {
                ["id"] = objectId,
                ["deleted"] = true
            };
        }

        private JObject ModifyObject(JObject parameters)
        {
            string objectId = parameters["id"]?.ToString();
            if (string.IsNullOrEmpty(objectId))
                throw new ArgumentException("Object ID is required");

            var doc = RhinoDoc.ActiveDoc;
            var obj = doc.Objects.Find(new Guid(objectId));

            if (obj == null)
                throw new InvalidOperationException($"Object with ID {objectId} not found");

            // Handle different modifications based on parameters
            bool modified = false;

            // Change name if provided
            if (parameters["name"] != null)
            {
                string name = parameters["name"].ToString();
                obj.Attributes.Name = name;
                modified = true;
            }

            // Change location if provided
            if (parameters["location"] != null && obj.Geometry != null)
            {
                double[] location = parameters["location"].ToObject<double[]>();

                // Get the current geometry
                var geometry = obj.Geometry;

                // Calculate the move transformation
                BoundingBox bbox = geometry.GetBoundingBox(true);
                Point3d center = bbox.Center;
                Point3d target = new Point3d(location[0], location[1], location[2]);
                Vector3d moveVector = target - center;

                // Apply the transformation
                Transform moveTransform = Transform.Translation(moveVector);
                geometry.Transform(moveTransform);

                modified = true;
            }

            // Apply scale if provided
            if (parameters["scale"] != null && obj.Geometry != null)
            {
                double[] scale = parameters["scale"].ToObject<double[]>();

                // Get the current geometry
                var geometry = obj.Geometry;

                // Calculate the center for scaling
                BoundingBox bbox = geometry.GetBoundingBox(true);
                Point3d center = bbox.Center;

                // Create scale transformation
                Transform scaleTransform = Transform.Scale(center, scale[0]);
                geometry.Transform(scaleTransform);

                // Update the object
                modified = true;
            }

            // Apply rotation if provided
            if (parameters["rotation"] != null && obj.Geometry != null)
            {
                double[] rotation = parameters["rotation"].ToObject<double[]>();

                // Get the current geometry
                var geometry = obj.Geometry;

                // Calculate the center for rotation
                BoundingBox bbox = geometry.GetBoundingBox(true);
                Point3d center = bbox.Center;

                // Create rotation transformations (in radians)
                Transform rotX = Transform.Rotation(rotation[0], Vector3d.XAxis, center);
                Transform rotY = Transform.Rotation(rotation[1], Vector3d.YAxis, center);
                Transform rotZ = Transform.Rotation(rotation[2], Vector3d.ZAxis, center);

                // Apply transformations
                geometry.Transform(rotX);
                geometry.Transform(rotY);
                geometry.Transform(rotZ);

                // Update the object
                modified = true;
            }

            if (modified)
            {
                // Update the object attributes if needed
                doc.Objects.ModifyAttributes(obj, obj.Attributes, true);
                // Update views
                doc.Views.Redraw();
            }

            return GetObjectInfo(new JObject { ["id"] = objectId });
        }

        private JObject ExecuteCode(JObject parameters)
        {
            string code = parameters["code"]?.ToString();
            if (string.IsNullOrEmpty(code))
                throw new ArgumentException("Code is required");

            // WARNING: Executing arbitrary code is a security risk
            // In a production environment, you should implement strict sandboxing
            // or avoid this feature entirely

            RhinoApp.WriteLine("Executing custom code is not implemented for security reasons");

            return new JObject
            {
                ["executed"] = false,
                ["message"] = "Code execution is disabled for security reasons"
            };
        }

        #endregion
    }
}