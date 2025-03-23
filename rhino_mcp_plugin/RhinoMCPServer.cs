using System;
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
                ["get_document_info"] = GetDocumentInfo,
                ["create_object"] = CreateObject,
                ["get_object_info"] = GetObjectInfo,
                ["get_selected_objects_info"] = GetSelectedObjectsInfo,
                ["delete_object"] = DeleteObject,
                ["modify_object"] = ModifyObject,
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

        private JObject GetDocumentInfo(JObject parameters)
        {
            RhinoApp.WriteLine("Getting document info...");

            var doc = RhinoDoc.ActiveDoc;

            var metaData = new JObject
            {
                ["name"] = doc.Name,
                ["date_created"] = doc.DateCreated,
                ["date_modified"] = doc.DateLastEdited,
                ["tolerance"] = doc.ModelAbsoluteTolerance,
                ["angle_tolerance"] = doc.ModelAngleToleranceDegrees,
                ["path"] = doc.Path,
                ["units"] = doc.ModelUnitSystem.ToString(),
            };

            var objectData = new JArray();

            // Collect minimal object information (limit to first 10 objects)
            int count = 0;
            foreach (var docObject in doc.Objects)
            {
                if (count >= 10) break;
                
                objectData.Add(Serializer.RhinoObject(docObject));
                count++;
            }

            var layerData = new JArray();

            count = 0;
            foreach (var docLayer in doc.Layers)
            {
                layerData.Add(new JObject
                {
                    ["id"] = docLayer.Id.ToString(),
                    ["name"] = docLayer.Name,
                    ["color"] = docLayer.Color.ToString(),
                    ["visible"] = docLayer.IsVisible,
                    ["locked"] = docLayer.IsLocked
                });
                count++;
            }


            var result = new JObject
            {
                ["meta_data"] = metaData,
                ["object_count"] = doc.Objects.Count,
                ["objects"] = objectData,
                ["layer_count"] = doc.Layers.Count,
                ["layers"] = layerData
            };

            RhinoApp.WriteLine($"Document info collected: {count} objects");
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
            var obj = getObjectByIdOrName(parameters);

            return Serializer.RhinoObject(obj);
        }

        private JObject GetSelectedObjectsInfo(JObject parameters)
        {
            var doc = RhinoDoc.ActiveDoc;
            var selectedObjs = doc.Objects.GetSelectedObjects(false, false);

            var result = new JArray();
            foreach (var obj in selectedObjs) result.Add(Serializer.RhinoObject(obj));
            
            return new JObject
            {
                ["selected_objects"] = result
            };
        }

        private RhinoObject getObjectByIdOrName(JObject parameters)
        {
            string objectId = parameters["id"]?.ToString();
            string objectName = parameters["name"]?.ToString();

            var doc = RhinoDoc.ActiveDoc;
            RhinoObject obj = null;

            if (!string.IsNullOrEmpty(objectId))
                obj = doc.Objects.Find(new Guid(objectId));
            else if (!string.IsNullOrEmpty(objectName))
            {
                // we assume there's only one of the object with the given name
                var objs = doc.Objects.GetObjectList(new ObjectEnumeratorSettings() { NameFilter = objectName }).ToList();
                if (objs == null) throw new InvalidOperationException($"Object with name {objectName} not found.");
                if (objs.Count > 1) throw new InvalidOperationException($"Multiple objects with name {objectName} found.");
                obj = objs[0];
            }

            if (obj == null)
                throw new InvalidOperationException($"Object with ID {objectId} not found");
            return obj;
        }

        private JObject DeleteObject(JObject parameters)
        {
            var obj = getObjectByIdOrName(parameters);

            var doc = RhinoDoc.ActiveDoc;
            bool success = doc.Objects.Delete(obj.Id, true);

            if (!success)
                throw new InvalidOperationException($"Failed to delete object with ID {obj.Id}");

            // Update views
            doc.Views.Redraw();

            return new JObject
            {
                ["id"] = obj.Id,
                ["name"] = obj.Name,
                ["deleted"] = true
            };
        }

        private JObject ModifyObject(JObject parameters)
        {
            var doc = RhinoDoc.ActiveDoc;
            var obj = getObjectByIdOrName(parameters);
            var geometry = obj.Geometry;
            var xform = Transform.Identity;

            // Handle different modifications based on parameters
            bool attributesModified = false;
            bool geometryModified = false;

            // Change name if provided
            if (parameters["new_name"] != null)
            {
                string name = parameters["new_name"].ToString();
                obj.Attributes.Name = name;
                attributesModified = true;
            }

            // Change location if provided
            if (parameters["location"] != null && obj.Geometry != null)
            {
                double[] location = parameters["location"].ToObject<double[]>();

                // Calculate the move transformation
                BoundingBox bbox = geometry.GetBoundingBox(true);
                Point3d center = bbox.Center;
                Point3d target = new Point3d(location[0], location[1], location[2]);
                Vector3d moveVector = target - center;

                // Apply the transformation
                xform *= Transform.Translation(moveVector);
                geometryModified = true;
            }

            // Apply scale if provided
            if (parameters["scale"] != null && obj.Geometry != null)
            {
                double[] scale = parameters["scale"].ToObject<double[]>();

                // Calculate the center for scaling
                BoundingBox bbox = geometry.GetBoundingBox(true);
                Point3d center = bbox.Center;
                Plane plane = Plane.WorldXY;
                plane.Origin = center;

                // Create scale transformation
                Transform scaleTransform = Transform.Scale(plane, scale[0], scale[1], scale[2]);
                xform *= scaleTransform;
                geometryModified = true;
            }

            // Apply rotation if provided
            if (parameters["rotation"] != null && obj.Geometry != null)
            {
                double[] rotation = parameters["rotation"].ToObject<double[]>();

                // Calculate the center for rotation
                BoundingBox bbox = geometry.GetBoundingBox(true);
                Point3d center = bbox.Center;

                // Create rotation transformations (in radians)
                Transform rotX = Transform.Rotation(rotation[0], Vector3d.XAxis, center);
                Transform rotY = Transform.Rotation(rotation[1], Vector3d.YAxis, center);
                Transform rotZ = Transform.Rotation(rotation[2], Vector3d.ZAxis, center);

                // Apply transformations
                xform *= rotX;
                xform *= rotY;
                xform *= rotZ;

                // Update the object
                geometryModified = true;
            }

            if (attributesModified)
            {
                // Update the object attributes if needed
                doc.Objects.ModifyAttributes(obj, obj.Attributes, true);
            }

            if (geometryModified)
            {
                // Update the object geometry if needed
                doc.Objects.Transform(obj, xform, true);
            }

            // Update views
            doc.Views.Redraw();

            return GetObjectInfo(new JObject { ["id"] = obj.Id });
        }

        #endregion
    }
}