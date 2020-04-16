from Canon.EDSDKLib import *
import time
from ctypes import *
import threading
import pythoncom
import queue
import util
from evfFrame import *

_camera = None
_errorMessageCallback = None
_methodQueue = queue.Queue()
_running = False
_comThread = None
_callbacksThread = None
_callbackQueue = queue.Queue()
_edsdk = None
_keep_liveview_alive = False

def _make_thread(target, name, args=[]):
    return threading.Thread(target=target, name=name, args=args)

def _run_com_thread():
    pythoncom.CoInitialize()

    while _running:
        try:
            while True:
                func, args, callback = _methodQueue.get(block=False)
                result = func(*args)
                
                if callback is not None:
                    _callbackQueue.put((callback, result))
        except queue.Empty:
            pass

        pythoncom.PumpWaitingMessages()
        time.sleep(0.05)

def _run_callbacks_thread():
    while _running:
        func, args = _callbackQueue.get(block=True)
        func(args)

def _run_in_com_thread(func, args=None, callback=None):
    if args is None:
        args = []
    _methodQueue.put((func, args, callback))

def initialize():
    global _running
    if _running:
        return
    _running = True

    global _comThread
    _comThread = _make_thread(_run_com_thread, "edsdk._run_com_thread")
    _comThread.start()

    global _callbacksThread
    _callbacksThread = _make_thread(_run_callbacks_thread, "edsdk._run_callbacks_thread")
    _callbacksThread.start()

    global _edsdk
    _edsdk = EDSDK()
    _edsdk.EdsInitializeSDK()
    
def terminate():
    global _running
    if not _running:
        return

    def helper():
        _callbacksThread.join()
        global _running
        _running = False

    _callbackQueue.put((lambda x: x, None))
    _run_in_com_thread(helper)

def setErrorMessageCallback(callback):
    global _errorMessageCallback
    _errorMessageCallback = callback


##############################################################################
#  Function:   _generate_file_name
#
#  Description:
#      Generates the image file name consists of date and file extension
#
#  Parameters:
#       In:    None
#
#  Returns:    file_name - image file name
##############################################################################
def _generate_file_name():
    now = datetime.datetime.now()
    file_name = "IMG_" + now.isoformat()[:-7].replace(':', '-') + ".jpg"
    return file_name


##############################################################################
#  Function:   _download_image
#
#  Description:
#      Using EDSDK, get the location of the image in camera, create the file
#      stream that processes transfer image from camera to PC, and download
#      the image
#
#  Parameters:
#       In:    image - the image reference
#
#  Returns:    None
##############################################################################
def _download_image(image):
    dir_info = _edsdk.EdsGetDirectoryItemInfo(image)
    #self.panelRight.resultBox.AppendText("Picture is taken.")
    file_name = _generate_file_name()
    stream = _edsdk.EdsCreateFileStream(file_name, 1, 2)
    _edsdk.EdsDownload(image, dir_info.size, stream)
    _edsdk.EdsDownloadComplete(image)
    #self.panelRight.resultBox.AppendText("Image is saved as " + file_name)
    _edsdk.EdsRelease(stream) 


ObjectHandlerType = WINFUNCTYPE(c_int,c_int,c_void_p,c_void_p)
##############################################################################
#  Function:   _handle_object
#
#  Description:
#      Handles the group of events where request notifications are issued to
#      create, delete or transfer image data stored in a camera or image files
#      on the memory card
#
#  Parameters:
#       In:    event - EdsObjectEvent event type supplemented
#              object - EdsBaseRef reference to object created by the event
#              context - EdsVoid any data needed for the application
#
#  Returns:    None
##############################################################################
def _handle_object(event, object, context):
    if event == _edsdk.ObjectEvent_DirItemRequestTransfer:
        _download_image(object)
    return 0
object_handler = ObjectHandlerType(_handle_object)


StateHandlerType = WINFUNCTYPE(c_int,c_int,c_int,c_void_p)
##############################################################################
#  Function:   _handle_state
#
#  Description:
#      Handles the group of events where notifications are issued regarding
#      changes in the state of a camera, such as activation of a shut-down
#      timer
#
#  Parameters:
#       In:    event - EdsStateEvent event type supplemented
#              state - EdsUInt32 pointer to the event data
#              context - EdsVoid any data needed for the application
#
#  Returns:    None
##############################################################################
def _handle_state(event, state, context):
    if event == _edsdk.StateEvent_WillSoonShutDown:
        #self.panelRight.resultBox.AppendText("Camera is about to shut off.")
        _edsdk.EdsSendCommand(context, 1, 0)
    return 0
state_handler = StateHandlerType(_handle_state)


PropertyHandlerType = WINFUNCTYPE(c_int,c_int,c_int,c_int,c_void_p)
##############################################################################
#  Function:   _handle_property
#
#  Description:
#      Handles the group of events where notifications are issued regarding
#      changes in the properties of a camera
#
#  Parameters:
#       In:    event - EdsPropertyEvent event type supplemented
#              property - EdsPropertyID property ID created by the event
#              param - EdsUInt32 used to identify information created by the
#                      event for custom function properties or other 
#                      properties that have multiple items of information
#              context - EdsVoid any data needed for the application
#
#  Returns:    None
##############################################################################
def _handle_property(event, property, param, context):
    return 0
property_handler = PropertyHandlerType(_handle_property)


class Camera:
    def __init__(self, id, camref):
        self.camref = camref
        self.id = id   
        self.device = c_void_p()
        self.is_evf_on = False
        self.keep_evf_alive = False
        self.running = False
        
    def connect(self):
        if self.running:
            return

        self.running = True

        #self.picture_thread = _make_thread(self.check_picture_queue, "edsdk.check_picture_queue", args=(self,))
        #self.picture_thread.start()

        #_run_in_com_thread(self.camref.connect)

        ## set the handlers
        _edsdk.EdsSetObjectEventHandler(self.camref, _edsdk.ObjectEvent_All, object_handler, None)
        _edsdk.EdsSetPropertyEventHandler(self.camref, _edsdk.PropertyEvent_All, property_handler, self.camref)
        _edsdk.EdsSetCameraStateEventHandler(self.camref, _edsdk.StateEvent_All, state_handler, self.camref)
        
        ## connect to the camera
        _edsdk.EdsOpenSession(self.camref)
        _edsdk.EdsSetPropertyData(self.camref, _edsdk.PropID_SaveTo, 0, 4, EdsSaveTo.Host.value)
        _edsdk.EdsSetCapacity(self.camref, EdsCapacity(10000000,512,1))

    def __del__(self):
        if self.camref is not None:
            _edsdk.EdsCloseSession(self.camref)
            _edsdk.EdsRelease(self.camref)
            _camera = None
            _running = False

    def shoot(self):
        global Wait_For_Image
        Wait_For_Image = True

        _edsdk.EdsSendCommand(self.camref, 0, 0)

    def startEvf(self):
        if not self.is_evf_on:
            ## start live view
            self.device = _edsdk.EvfOutputDevice_PC
            self.device = _edsdk.EdsSetPropertyData(self.camref, _edsdk.PropID_Evf_OutputDevice, 0, sizeof(c_uint), self.device)
            _keep_liveview_alive = True

    def _download_evf(self):
        evfStream = _edsdk.EdsCreateMemoryStream(0)
        self.evfFrame = EvfFrame()
        evfImageRef = _edsdk.EdsCreateEvfImageRef(evfStream)
        _edsdk.EdsDownloadEvfImage(self.camref, evfImageRef)
        
        dataset = EvfDataSet()
        #dataset.zoom = _edsdk.EdsGetPropertyData(evfImageRef,_edsdk.PropID_Evf_Zoom, 0, sizeof(c_uint), c_uint(dataset.zoom))
        #dataset.imagePosition = _edsdk.EdsGetPropertyData(evfImageRef,_edsdk.PropID_Evf_ImagePosition, 0, sizeof(EdsPoint),dataset.imagePosition)
        #dataset.zoomRect = _edsdk.EdsGetPropertyData(evfImageRef,_edsdk.PropID_Evf_ZoomRect, 0, sizeof(EdsRect), dataset.zoomRect)
        #dataset.sizeJpgLarge = _edsdk.EdsGetPropertyData(evfImageRef,_edsdk.PropID_Evf_CoordinateSystem, 0, sizeof(EdsSize),dataset.sizeJpgLarge)

        image_info = _edsdk.EdsGetImageInfo(evfImageRef, EdsImageSource.RAWFullView.value)
        output_size = EdsSize()
        output_size.width = image_info.effectiveRect.width
        output_size.height = image_info.effectiveRect.height

        image_stream = _edsdk.EdsGetImage(evfImageRef, EdsImageSource.RAWFullView.value, EdsTargetImageType.RGB.value, image_info.effectiveRect, output_size)

        _edsdk.EdsRelease(evfImageRef)
        _edsdk.EdsRelease(evfStream)

        self.evfFrame.onDrawImage(image_data_bytearray)
        self.evfFrame.Show()

    def liveViewMemoryView(self):
        return memoryview(self.camref)
    
class CameraList:
    def __init__(self):
        self.list = c_void_p(None)
        self.list = _edsdk.EdsGetCameraList()
        self.cam_model_list = []
        self.selected_camera = None
        self.count = _edsdk.EdsGetChildCount(self.list)

        if self.count == 0:
            util.set_dialog("There is no camera connected.")
        else:
            ## transfer EDSDK camera object to custom camera object
            for i in range(self.count):
                self.cam_model_list.append(Camera(i, _edsdk.EdsGetChildAtIndex(self.list, i)))

        _edsdk.EdsRelease(self.list)

    def get_count(self):
        return self.count

    def get_camera_by_index(self, index):
        return cam_model_list[index]

    def get_camera_by_id(self, id):
        if id not in range(len(self.cam_model_list)):
            for model in self.cam_model_list:
                if model.id == id:
                    return model
        else:
            index = id
            while index in range(len(self.cam_model_list)):
                model_index = self.cam_model_list[index]
                if model_index.id == id:
                    return model_index
                elif model_index.id > id:
                    index -= 1
                else:
                    index += 1
        return None

    def set_selected_cam_by_id(self, id):
        self.selected_camera = self.get_camera_by_id(id)
        self.selected_camera.connect()
        _camera = self.selected_camera

    def disconnect_cameras(self):
        for cam in self.cam_model_list:
            del cam

class EvfDataSet(Structure):
    _fields_ = [('stream', c_void_p),
               ('zoom', c_uint),
               ('zoomRect', EdsRect),
               ('imagePosition', EdsPoint),
               ('sizeJpgLarge', EdsSize)]

