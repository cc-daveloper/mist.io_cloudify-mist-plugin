from cloudify import ctx
from cloudify.decorators import operation
from cloudify.exceptions import NonRecoverableError, RecoverableError
from mistclient import MistClient
from time import sleep
import connection
import constants
import keypair

@operation
def creation_validation(**_):

    """ This checks that all user supplied info is valid """
    ctx.logger.info('Checking validity of info')
    mist_client = connection.MistConnectionClient()
    try:
        client = mist_client.client
    except:
        raise NonRecoverableError('Credentials failed')

    for property_key in constants.INSTANCE_REQUIRED_PROPERTIES:
        if property_key not in ctx.node.properties:
            raise NonRecoverableError(
                '{0} is a required input. Unable to create.'.format(key))
    backend = client.backends(id=ctx.node.properties['backend_id'])
    if not len(backend):
        raise NonRecoverableError(
            '{0} backend was not found.'.format(ctx.node.properties['backend_id']))
    image = ""
    for im in backend[0].images:
        if im[id] == ctx.node.properties['image_id']:
            image = im
            break
    if not image:
        raise NonRecoverableError(
            'image_id {0} not found.'.format(ctx.node.properties['image_id']))
    size = ""
    for si in backend[0].sizes:
        if si[id] == ctx.node.properties['size_id']:
            size = si
            break
    if not size:
        raise NonRecoverableError(
            'size_id {0} not found.'.format(ctx.node.properties['size_id']))
    location = ""
    for lo in backend[0].locations:
        if lo[id] == ctx.node.properties['location_id']:
            location = lo
            break
    if not location:
        raise NonRecoverableError(
            'location_id {0} not found.'.format(ctx.node.properties['location_id']))

    machines = backend[0].machines(search=ctx.node.properties["name"])
    if ctx.node.properties['use_external_resource'] and not len(machines):
        raise NonRecoverableError(
            'machine {0} not found.'.format(ctx.node.properties["name"]))
    if not ctx.node.properties['use_external_resource'] and len(machines):
        raise NonRecoverableError(
            'machine {0} exists.'.format(ctx.node.properties["name"]))
    if ctx.node.properties['use_external_resource'] and len(machines):
        if machines[0].info["state"] == "running":
            pass
        elif machines[0].info["state"] == "stopped":
            machines[0].start()
            delay = 0
            while True:
                sleep(10)
                backend[0].update_machines()
                if backend[0].machines(search=ctx.node.properties["name"])[0].info["state"] == "running":
                    break
                elif delay == 5:
                    raise NonRecoverableError(
                        'machine {0} in stopped state.'.format(ctx.node.properties["name"]))
                delay += 1
        else:
            raise NonRecoverableError(
                'machine {0} error state.'.format(ctx.node.properties["name"]))


@operation
def create(**_):
    mist_client = connection.MistConnectionClient()
    client = mist_client.client
    # backend = client.backends(id=ctx.node.properties['backend_id'])[0]
    backend = mist_client.backend
    if ctx.node.properties['use_external_resource']:
        machine = mist_client.machine
        ctx.instance.runtime_properties['ip'] = machine.info["public_ips"][0]
        ctx.instance.runtime_properties['networks'] = {
            "default": machine.info["public_ips"][0]}
        ctx.logger.info('External machine attached to ctx')
        return
    machines = backend.machines(search=ctx.node.properties["name"])
    if len(machines):
        for m in machines:
            if m.info["state"] in  ["running","stopped"]:
                raise NonRecoverableError(
                    "Machine with name {0} exists".format(ctx.node.properties["name"]))
    
    key=""
    if "key" in ctx.node.properties:
        key = client.keys(search=ctx.node.properties["key"])
        if len(key):
            key = key[0]
        else:
            raise NonRecoverableError("key not found")
    else:
        keys = client.keys()
        for k in keys:
            if k.is_default:
                ctx.logger.info('Using default key ')
                key = k
        if not key:
            ctx.logger.info(
                'No key found. Trying to generate one and add one.')
            private = client.generate_key()
            client.add_key(
                key_name=ctx.node.properties["name"], private=private)
            key = client.keys(search=ctx.node.properties["name"])[0]
    print key        
    job_id = backend.create_machine(async=True, name=ctx.node.properties["name"], key=key,
                                    image_id=ctx.node.properties["image_id"],
                                    location_id=ctx.node.properties[
        "location_id"],
        size_id=ctx.node.properties["size_id"])
    job_id = job_id.json()["job_id"]
    job = client.get_job(job_id)
    timer=0
    while True:
        if job["summary"]["probe"]["success"]:
            break
        if job["summary"]["create"]["error"] or job["summary"]["probe"]["error"]:
            ctx.logger.error('Error on machine creation ')
            raise NonRecoverableError("Not able to create machine")
        sleep(10)
        job = client.get_job(job_id)
        print job["summary"]
        timer+=1
        if timer >=60:   # timeout
            raise NonRecoverableError("Timeout.Not able to create machine.")
    
    machine = mist_client.machine
    ctx.instance.runtime_properties['ip'] = machine.info["public_ips"][0]
    ctx.instance.runtime_properties['networks'] = {
        "default": machine.info["public_ips"][0]}
    ctx.logger.info('Machine created')


@operation
def start(**kwargs):
    connection.MistConnectionClient().machine.start()
    ctx.logger.info('Machine started')


@operation
def stop(**kwargs):
    connection.MistConnectionClient().machine.stop()
    ctx.logger.info('Machine stopped')


@operation
def delete(**kwargs):
    connection.MistConnectionClient().machine.destroy()
    ctx.logger.info('Machine destroyed')


# @operation
# def creation_validation(nova_client, args, **kwargs):
