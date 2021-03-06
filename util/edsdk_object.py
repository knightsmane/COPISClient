#!/usr/bin/env python3

import time
import utils

import wx
from ctypes import *
from util.Canon.EDSDKLib import *

_edsdk = None
_console = None
_running = False


def initialize(console):
    if _running:
        return

    global _edsdk
    global _console
    _console = console

    try:
        _edsdk = EDSDK()
        _edsdk.EdsInitializeSDK()
    except Exception as e:
        _console.print('An exception occurred while initializing Canon API: ' + e.args[0])


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
    file_name = 'IMG_' + now.isoformat()[:-7].replace(':', '-') + '.jpg'
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
    try:
        dir_info = _edsdk.EdsGetDirectoryItemInfo(image)
        file_name = _generate_file_name()
        stream = _edsdk.EdsCreateFileStream(file_name, 1, 2)
        _edsdk.EdsDownload(image, dir_info.size, stream)
        _edsdk.EdsDownloadComplete(image)
        _edsdk.EdsRelease(stream)
        _console.print('Image is saved as ' + file_name + '.')
    except Exception as e:
        _console.print('An exception occurred while downloading an image: ' + e.args[0])


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
        try:
            _edsdk.EdsSendCommand(context, 1, 0)
        except Exception as e:
            _console.print('An exception occurred while handling the state change event: ' + e.args[0])
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
    def __init__(self, camid, camref):
        self.camref = camref
        self.camid = camid
        self.device = c_void_p()
        self.is_evf_on = False
        self.running = False

    def connect(self):
        if self.running:
            return

        self.running = True

        try:
            # set the handlers
            _edsdk.EdsSetObjectEventHandler(self.camref, _edsdk.ObjectEvent_All, object_handler, None)
            _edsdk.EdsSetPropertyEventHandler(self.camref, _edsdk.PropertyEvent_All, property_handler, self.camref)
            _edsdk.EdsSetCameraStateEventHandler(self.camref, _edsdk.StateEvent_All, state_handler, self.camref)

            # connect to the camera
            _edsdk.EdsOpenSession(self.camref)
            _edsdk.EdsSetPropertyData(self.camref, _edsdk.PropID_SaveTo, 0, 4, EdsSaveTo.Host.value)
            _edsdk.EdsSetCapacity(self.camref, EdsCapacity(10000000, 512, 1))
        except Exception as e:
            _console.print('An exception occurred while connecting to a camera' + str(self.camid + 1) + ': ' + e.args[0])

    def __del__(self):
        if self.camref is not None:
            try:
                _edsdk.EdsCloseSession(self.camref)
                _edsdk.EdsRelease(self.camref)
                _running = False
            except Exception as e:
                _console.print('An exception occurred while disconnecting a camera' + str(self.camid + 1) + ': ' + e.args[0])

    def shoot(self):
        try:
            _edsdk.EdsSendCommand(self.camref, 0, 0)
        except Exception as e:
            _console.print('An exception occurred while taking a photo with camera' + str(self.camid + 1) + ': ' + e.args[0])

    def startEvf(self):
        if not self.is_evf_on:
            try:
                # start live view
                self.device = _edsdk.EvfOutputDevice_PC
                self.device = _edsdk.EdsSetPropertyData(self.camref, _edsdk.PropID_Evf_OutputDevice, 0, sizeof(c_uint), self.device)
                global _keep_liveview_alive
                _keep_liveview_alive = True
                self.evf_frame_displayed = False

                self.evfStream = _edsdk.EdsCreateMemoryStream(0)
                self.evfImageRef = _edsdk.EdsCreateEvfImageRef(self.evfStream)
            except Exception as e:
                _console.print('An exception occurred while starting a live view with camera' + str(self.camid + 1) + ': ' + e.args[0])

            time.sleep(0.5)
            self.download_evf()
            _console.print('Live view is on.')

    def download_evf(self):
        time.sleep(0.1)
        try:
            _edsdk.EdsDownloadEvfImage(self.camref,self.evfImageRef)

            #dataset = EvfDataSet()
            #dataset.zoom = _edsdk.EdsGetPropertyDat(evfImageRef,_edsdk.PropID_Evf_Zoom, 0, sizeo(c_uint), c_uint(dataset.zoom))
            #dataset.imagePosition = _edsdk.EdsGetPropertyDat(evfImageRef,_edsdk.PropID_Evf_ImagePosition, 0,sizeof(EdsPoint),dataset.imagePosition)
            #dataset.zoomRect = _edsdk.EdsGetPropertyDat(evfImageRef,_edsdk.PropID_Evf_ZoomRect, 0, sizeo(EdsRect), dataset.zoomRect)
            #dataset.sizeJpgLarge = _edsdk.EdsGetPropertyDat(evfImageRef,_edsdk.PropID_Evf_CoordinateSystem, 0,sizeof(EdsSize),dataset.sizeJpgLarge)

            output_length = _edsdk.EdsGetLength(self.evfStream)
            image_data = (c_ubyte * output_length.value)()
            image_data_pointer = _edsdk.EdsGetPointer(self.evfStream, image_data)
            self.img_byte_data = bytearray(string_at(image_data_pointer, output_length.value))
        except Exception as e:
            _console.print('An exception occurred while downloading a live view image with camera' + str(self.camid + 1) + ': ' + e.args[0])


    def end_evf(self):
        try:
            _edsdk.EdsRelease(self.evfImageRef)
            _edsdk.EdsRelease(self.evfStream)
            dataType_size = _edsdk.EdsGetPropertySize(self.camref, _edsdk.PropID_Evf_DepthOfFieldPreview, 0)
            _edsdk.EdsSetPropertyData(self.camref, _edsdk.PropID_Evf_DepthOfFieldPreview, 0, dataType_size['size'], _edsdk.EvfDepthOfFieldPreview_OFF)
            self.is_evf_on = False
            time.sleep(1)

            device = c_uint32()
            device.value &= ~_edsdk.EvfOutputDevice_PC
            _edsdk.EdsSetPropertyData(self.camref, _edsdk.PropID_Evf_OutputDevice, 0, sizeof(device), device.value)
            _console.print('Live view is off.')
        except Exception as e:
            _console.print('An exception occurred while closing a live view with camera' + str(self.camid + 1) + ': ' + e.args[0])


class CameraList:
    def __init__(self):
        self.list = c_void_p(None)

        try:
            self.list = _edsdk.EdsGetCameraList()
            self.cam_model_list = []
            self.selected_camera = None
            self.count = _edsdk.EdsGetChildCount(self.list)

            if self.count != 0:
                # transfer EDSDK camera object to custom camera object
                for i in range(self.count):
                    self.cam_model_list.append(Camera(i, _edsdk.EdsGetChildAtIndex(self.list, i)))

            _edsdk.EdsRelease(self.list)
        except Exception as e:
            _console.print('An exception occurred while getting the camera list: ' + e.args[0])

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

        global _camera
        _camera = self.selected_camera

    def terminate(self):
        for cam in self.cam_model_list:
            del cam

        try:
            _edsdk.EdsTerminateSDK()
            global _running
            _running = False
        except Exception as e:
            _console.print('An exception occurred while terminating Canon API: ' + e.args[0])


class EvfDataSet(Structure):
    _fields_ = [('stream', c_void_p),
               ('zoom', c_uint),
               ('zoomRect', EdsRect),
               ('imagePosition', EdsPoint),
               ('sizeJpgLarge', EdsSize)]
